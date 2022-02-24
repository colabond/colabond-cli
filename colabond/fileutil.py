import os


def scan_current_file_state():
    project_file_state = dict()
    # scan current directory recursively
    for root, dirs, files in os.walk("."):
        for file in files:
            # get only root directory from root
            root_parts = os.path.split(root)

            if len(root_parts) > 1:
                root_dir = root_parts[1]
                if root_dir in [
                    ".colabond",
                    ".git",
                    ".idea",
                    ".ipynb_checkpoints",
                    ".node_modules",
                    ".vscode",
                    ".vscode-test",
                    "__pycache__",
                ]:
                    continue

            filename = os.path.join(root, file)
            filedatetime = os.path.getmtime(filename)
            project_file_state[filename] = filedatetime
    return project_file_state
