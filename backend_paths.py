import os


def get_project_root(script_dir=None):
    """Return repository root path based on script location."""
    base = script_dir or os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(base)


def get_dashboard_public_dir(script_dir=None):
    """Return absolute path to rs-dashboard/public."""
    return os.path.join(get_project_root(script_dir), "rs-dashboard", "public")


def get_dashboard_data_path(script_dir=None):
    """Return absolute path to rs-dashboard/public/data.json."""
    return os.path.join(get_dashboard_public_dir(script_dir), "data.json")


def get_dashboard_tab_data_dir(script_dir=None):
    """Return absolute path to rs-dashboard/public/tab-data."""
    return os.path.join(get_dashboard_public_dir(script_dir), "tab-data")


def get_dashboard_tab_data_path(artifact_name, script_dir=None):
    """Return absolute path to a tab artifact JSON file."""
    return os.path.join(
        get_dashboard_tab_data_dir(script_dir), f"{artifact_name}.json"
    )


def get_dashboard_tab_manifest_path(script_dir=None):
    """Return absolute path to rs-dashboard/public/tab-data/manifest.json."""
    return os.path.join(get_dashboard_tab_data_dir(script_dir), "manifest.json")
