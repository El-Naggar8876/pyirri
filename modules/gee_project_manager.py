"""
Google Earth Engine project storage for PyIrri.

This module persists and retrieves irrigation project documents as
``ee.FeatureCollection`` assets in Google Earth Engine.  It is intentionally
self-contained and credential-free: secrets are loaded from
``st.secrets["gee"]`` (Streamlit Cloud / local ``.streamlit/secrets.toml``) or
from environment variables (``GEE_PROJECT_ID``, ``GEE_SERVICE_ACCOUNT``,
``GEE_PRIVATE_KEY``).  When no credentials are configured the application
still runs; project save/load is simply disabled and a friendly notice is
shown to the user.

Asset folder used by this distribution:
    projects/<GEE_PROJECT_ID>/assets/SprinklerDesignSoftwareX
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import streamlit as st

try:
    import ee  # type: ignore
    _EE_AVAILABLE = True
except Exception:  # noqa: BLE001
    ee = None  # type: ignore
    _EE_AVAILABLE = False


# Distribution-specific asset folder name.  Distinct from any other deployment
# so it cannot interfere with parallel installations of the tool.
ASSET_FOLDER_NAME = "SprinklerDesignSoftwareX"


def _load_credentials() -> dict[str, str] | None:
    """Load GEE credentials from Streamlit secrets or environment.

    Returns a dict with keys ``project_id``, ``service_account``,
    ``private_key`` if a complete configuration is found, otherwise ``None``.
    """
    project_id = service_account = private_key = None

    try:
        gee_secrets = st.secrets.get("gee", {})  # type: ignore[union-attr]
        project_id = gee_secrets.get("project_id")
        service_account = gee_secrets.get("service_account")
        private_key = gee_secrets.get("private_key")
    except Exception:  # noqa: BLE001
        # secrets.toml not configured — fall through to env vars
        pass

    project_id = project_id or os.environ.get("GEE_PROJECT_ID")
    service_account = service_account or os.environ.get("GEE_SERVICE_ACCOUNT")
    private_key = private_key or os.environ.get("GEE_PRIVATE_KEY")

    if project_id and service_account and private_key:
        return {
            "project_id": project_id,
            "service_account": service_account,
            "private_key": private_key,
        }
    return None


class GEEProjectManager:
    """Save and load irrigation projects as GEE assets."""

    def __init__(self) -> None:
        self.initialized = False
        self.error_message: str | None = None
        self.project_id: str | None = None
        self.base_folder: str | None = None

    # ------------------------------------------------------------------ init
    def initialize(self) -> bool:
        if self.initialized:
            return True
        if not _EE_AVAILABLE:
            self.error_message = "earthengine-api is not installed."
            return False

        creds = _load_credentials()
        if creds is None:
            self.error_message = (
                "Google Earth Engine credentials are not configured. "
                "Add them to .streamlit/secrets.toml or environment variables "
                "to enable cloud project storage."
            )
            return False

        try:
            credentials = ee.ServiceAccountCredentials(
                creds["service_account"], key_data=creds["private_key"]
            )
            ee.Initialize(credentials, project=creds["project_id"])
            self.project_id = creds["project_id"]
            self.base_folder = (
                f"projects/{self.project_id}/assets/{ASSET_FOLDER_NAME}"
            )
            self._ensure_folder(self.base_folder)
            self.initialized = True
            return True
        except Exception as exc:  # noqa: BLE001
            self.error_message = f"GEE initialization failed: {exc}"
            return False

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _ensure_folder(path: str) -> None:
        try:
            ee.data.getAsset(path)
        except Exception:  # noqa: BLE001
            try:
                ee.data.createAsset({"type": "Folder"}, path)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _sanitize(name: str) -> str:
        return "".join(c if c.isalnum() else "_" for c in name).strip("_") or "project"

    def _asset_path(self, project_name: str) -> str:
        assert self.base_folder is not None
        return f"{self.base_folder}/{self._sanitize(project_name)}"

    # ----------------------------------------------------------------- save
    def save_project(self, project_name: str, data: dict[str, Any]) -> tuple[bool, str]:
        if not self.initialize():
            return False, self.error_message or "GEE not available."

        try:
            payload = {
                "project_name": project_name,
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "data_json": json.dumps(data, default=str),
            }
            feature = ee.Feature(None, payload)
            fc = ee.FeatureCollection([feature])
            asset_path = self._asset_path(project_name)
            try:
                ee.data.deleteAsset(asset_path)
            except Exception:  # noqa: BLE001
                pass
            task = ee.batch.Export.table.toAsset(
                collection=fc, description=f"save_{project_name}", assetId=asset_path
            )
            task.start()
            return True, f"Project '{project_name}' submitted to GEE."
        except Exception as exc:  # noqa: BLE001
            return False, f"Save failed: {exc}"

    # ----------------------------------------------------------------- load
    def list_projects(self) -> list[str]:
        if not self.initialize():
            return []
        try:
            assets = ee.data.listAssets({"parent": self.base_folder})
            return [a["id"].split("/")[-1] for a in assets.get("assets", [])]
        except Exception:  # noqa: BLE001
            return []

    def load_project(self, project_name: str) -> tuple[bool, dict[str, Any] | str]:
        if not self.initialize():
            return False, self.error_message or "GEE not available."
        try:
            fc = ee.FeatureCollection(self._asset_path(project_name))
            info = fc.first().toDictionary().getInfo()
            data = json.loads(info.get("data_json", "{}"))
            return True, data
        except Exception as exc:  # noqa: BLE001
            return False, f"Load failed: {exc}"


# --------------------------------------------------------------- singletons
_gee_manager: GEEProjectManager | None = None


def get_gee_manager() -> GEEProjectManager:
    global _gee_manager
    if _gee_manager is None:
        _gee_manager = GEEProjectManager()
    return _gee_manager


# --------------------------------------------------------- minimal sidebar UI
def show_project_manager_ui() -> None:
    """Compact GEE project save/load UI, callable from the home page."""
    mgr = get_gee_manager()
    with st.expander("☁️ Cloud Projects (Google Earth Engine)", expanded=False):
        if not mgr.initialize():
            st.info(mgr.error_message or "Cloud storage not configured.")
            return

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Project name", key="_gee_save_name")
            if st.button("💾 Save current project", key="_gee_save_btn"):
                if name and "project_data" in st.session_state:
                    ok, msg = mgr.save_project(name, st.session_state.project_data)
                    (st.success if ok else st.error)(msg)

        with col2:
            projects = mgr.list_projects()
            if projects:
                chosen = st.selectbox("Load project", projects, key="_gee_load_sel")
                if st.button("📂 Load", key="_gee_load_btn"):
                    ok, payload = mgr.load_project(chosen)
                    if ok and isinstance(payload, dict):
                        st.session_state.project_data = payload
                        st.success(f"Loaded '{chosen}'.")
                        st.rerun()
                    else:
                        st.error(str(payload))
            else:
                st.caption("No saved projects yet.")
