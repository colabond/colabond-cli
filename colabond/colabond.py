import base64
import getpass
import json
import os
import readline
import sys
import tarfile

import colabond.fileutil as fileutil
import requests
import termcolor
import yaml

# If windows, execute this statement to enable colors
if os.name == "nt":
    os.system("color")

HOST = "https://colabond.co"


BANNER = """
╓──────────────────────────────────────────────────────────╖
║            _____     __     __                __         ║
║           / ___/__  / /__ _/ /  ___  ___  ___/ /         ║
║          / /__/ _ \/ / _ `/ _ \/ _ \/ _ \/ _  /          ║
║          \___/\___/_/\_,_/_.__/\___/_//_/\_,_/           ║
║                                                          ║
╟──────────────────────────────────────────────────────────╢
│                    Interactive prompt                    │
╚──────────────────────────────────────────────────────────╝
"""

PROMPT = "◎──────◎ Enter command:"


def auth(email, password):
    # find user by email and password
    url = HOST + "/api/v1/auth"
    data = {"email": email, "password": password}
    r = requests.post(url, data=data)

    if r.json().get("token", None):
        return r.json()
    else:
        print("Invalid email or password")
        sys.exit(1)


def display_help():
    print("Usage: colabond <command>")
    print("Commands:")
    print("  connect    Connect to the project in colabond")
    print("  exec       Send a command the server for execution")
    print("         -i  Run in interactive mode")
    print("  full-sync  Perform a full sync between local project and the server")
    print("  help       Show this help message")
    print("  signin     Sign in to colabond")
    print("  signout    Sign out of colabond")


# decorator to ensure that the project is running based on the project_id
# in the colabond.yaml file
def require_agent_run(func):
    def wrapper(*args, **kwargs):
        # First, ensure project is running
        cred = get_cred()
        project_id = yaml.load(open(".colabond/colabond.yaml", "r"), yaml.FullLoader)[
            "project_id"
        ]

        # post request to check if project_id exists
        data = {
            "project_id": project_id,
            "email": cred["email"],
            "token": cred["token"],
        }
        res = requests.post(HOST + "/api/v1/projects", data=data)
        res = res.json()

        if res["execution_status"] != "running":
            print(
                termcolor.colored(
                    f"Colabond agent for id {project_id} is not running. Please ensure it is running in remote kernel.",
                    "red",
                )
            )
            raise Exception("Colabond agent is not running")
        return func(*args, **kwargs)

    return wrapper


def signin():
    # prompt for email and password
    email = input("Email: ")
    password = getpass.getpass("Password: ")
    res = auth(email, password)
    token = res["token"]

    # create ".colabond" directory in user's home directory
    user_dir = os.path.expanduser("~")
    os.makedirs(os.path.join(user_dir, ".colabond"), exist_ok=True)

    # write email and token to ".colabond/cred.yaml"
    cred_file = os.path.join(user_dir, ".colabond/cred.yaml")
    with open(cred_file, "w") as f:
        yaml.dump({"email": email, "token": token}, f)

    print("Successfully signed in")


def require_auth(func):
    """
    function as decorator to ensure that the user is signed in
    """

    def wrapper(*args, **kwargs):
        # check if the user is signed in
        user_dir = os.path.expanduser("~")
        if not os.path.exists(os.path.join(user_dir, ".colabond/cred.yaml")):
            # print in red
            print(
                termcolor.colored(
                    "You are not signed in. Run 'colabond signin' first.", "red"
                )
            )
            sys.exit(1)

        # if the user is signed in, execute the function
        return func(*args, **kwargs)

    return wrapper


def require_connected(func):
    """
    function as decorator to ensure that the user has initialized their project
    """

    def wrapper(*args, **kwargs):
        # check if the user has initialized their project
        if not os.path.exists(".colabond/colabond.yaml"):
            print(
                termcolor.colored(
                    "You have not connected your project. Run 'colabond connect'", "red"
                )
            )
            sys.exit(1)

        # if the user has initialized their project, execute the function
        return func(*args, **kwargs)

    return wrapper


# check changes (deletion, addition, modification)
def check_changes():
    # read ".colabond/file_state.json"
    with open(".colabond/file_info", "r") as f:
        old_file_state = json.load(f)
    # scan current directory recursively
    current_file_state = fileutil.scan_current_file_state()
    added_files = []
    modified_files = []
    deleted_files = []
    for filename in current_file_state:
        if filename not in old_file_state:
            added_files.append(
                {"filename": filename, "datetime": current_file_state[filename]}
            )
        elif current_file_state[filename] != old_file_state[filename]:
            modified_files.append(
                {"filename": filename, "datetime": current_file_state[filename]}
            )
    for filename in old_file_state:
        if filename not in current_file_state:
            deleted_files.append(
                {"filename": filename, "datetime": old_file_state[filename]}
            )
    return added_files, modified_files, deleted_files


def commit_changes(added_files, modified_files, deleted_files):
    # read ".colabond/file_state.json"
    with open(".colabond/file_info", "r") as f:
        old_file_state = json.load(f)
    # update old_file_state
    for added_file in added_files:
        old_file_state[added_file["filename"]] = added_file["datetime"]
    for modified_file in modified_files:
        old_file_state[modified_file["filename"]] = modified_file["datetime"]
    for deleted_file in deleted_files:
        del old_file_state[deleted_file["filename"]]
    # (re)write ".colabond/file_state.json"
    with open(".colabond/file_info", "w") as f:
        json.dump(old_file_state, f)


@require_auth
def get_cred():
    # get token from user's ".colabond/token" file as string
    user_dir = os.path.expanduser("~")
    with open(os.path.join(user_dir, ".colabond/cred.yaml"), "r") as f:
        cred = yaml.load(f, Loader=yaml.FullLoader)
    return cred


@require_auth
def signout():
    # remove the token file
    user_dir = os.path.expanduser("~")
    os.remove(os.path.join(user_dir, ".colabond/token"))
    print("Successfully signed out")


@require_auth
def connect():
    print("Connecting to the project")

    project_id = input("Project id (from colabond dashboard): ")

    cred = get_cred()

    # post request to check if project_id exists
    data = {"project_id": project_id, "email": cred["email"], "token": cred["token"]}
    res = requests.post(HOST + "/api/v1/projects", data=data)

    if not bool(res):
        print("Project does not exist. Aborting.")
        sys.exit(1)

    config = {
        "email": cred["email"],
        "project_id": project_id,
    }

    # create ".colabond" directory in current directory
    os.makedirs(".colabond", exist_ok=True)

    # write a json file containing file name and modification time to ".colabond/file_info"
    with open(".colabond/file_info", "w") as f:
        # get a list of all files in the current directory recursively
        files = []
        for root, dirs, filenames in os.walk("."):
            for filename in filenames:
                if filename != "colabond.yaml":
                    # if not child of ".colabond" or ".git"
                    if not root.startswith(".colabond") and not root.startswith(".git"):
                        filename = os.path.join(root, filename)
                        modified_time = os.path.getmtime(filename)
                        file_info = {
                            "filename": filename,
                            "modified_time": modified_time,
                        }
                        files.append(file_info)

        # write the list of files to ".colabond/file_info" as json
        f.write(json.dumps(files))

    # Create a new colabond.yaml file
    with open(".colabond/colabond.yaml", "w") as f:
        f.write(yaml.dump(config))


@require_connected
@require_auth
def exec(command):
    if not command:
        print("Error: no command specified")
        sys.exit(1)

    # make a POST request to the server
    # use the project_id and email from the colabond.yaml file
    with open(".colabond/colabond.yaml", "r") as f:
        y = yaml.load(f, yaml.FullLoader)

    cred = get_cred()
    project_id = y["project_id"]

    # get file changes
    added_files, modified_files, deleted_files = check_changes()
    if len(added_files) + len(modified_files) + len(deleted_files) > 0:
        print("\nCommitting changes...")
    for f in added_files:
        print(termcolor.colored("[+] " + f["filename"][2:], "green"))
    for f in modified_files:
        print(termcolor.colored("[M] " + f["filename"][2:], "yellow"))
    for f in deleted_files:
        print(termcolor.colored("[-] " + f["filename"][2:], "red"))
    commit_changes(added_files, modified_files, deleted_files)

    # create .colabond/files.tar.gz from added_files and modified_files
    with tarfile.open(".colabond/files.tar.gz", "w:gz") as tar:
        for f in added_files:
            tar.add(f["filename"])
        for f in modified_files:
            tar.add(f["filename"])

    # if .colabond/files.tar.gz exists, open it and convert to base64
    files = ""
    if os.path.exists(".colabond/files.tar.gz"):
        with open(".colabond/files.tar.gz", "rb") as f:
            files = f.read()
            files = base64.b64encode(files).decode("utf-8")

    # if there is any file changes, send them to the server
    if len(added_files) + len(modified_files) + len(deleted_files) > 0:
        url = HOST + "/api/v1/project_set_files"
        # send .colabond/files.tar.gz
        data = {
            "project_id": project_id,
            "files": files,
            "email": cred["email"],
        }
        r = requests.post(url, data=data)

    # update project's execution_command to the command
    url = HOST + "/api/v1/project_set_command"
    data = {
        "project_id": project_id,
        "email": cred["email"],
        "command": command,
        # "files": files,
        "token": cred["token"],
    }
    r = requests.post(url, data=data)

    # if status is "failed", print the error message
    if r.json()["status"] == "error":
        print(termcolor.colored(r.json()["message"], "red"))
    else:
        # if the request was successful, print the response
        # Print in dimmed
        print("\033[2m" + f"\nCommand set: `{command}`" + "\033[0m")

        # remove .colabond/files.tar.gz if it exists since it is no longer needed
        if os.path.exists(".colabond/files.tar.gz"):
            os.remove(".colabond/files.tar.gz")


@require_auth
@require_connected
@require_agent_run
def full_sync():
    """
    Syncs the local files with the server fully. Update current file state
    in .colabond/file_info.
    """

    fst = fileutil.scan_current_file_state()

    # Update the file_info file with the current file state
    with open(".colabond/file_info", "w") as f:
        f.write(json.dumps(fst))

    # create tarfile to hold all files in the project directory
    with tarfile.open(".colabond/files.tar.gz", "w:gz") as tar:
        for f, _ in fst.items():
            tar.add(f)

    # Encode the tarfile as base64
    # TODO: better file transfer instead of using base64
    with open(".colabond/files.tar.gz", "rb") as f:
        files = f.read()
        files = base64.b64encode(files).decode("utf-8")

    # remove the tarfile as we don't need it anymore
    os.remove(".colabond/files.tar.gz")
    url = HOST + "/api/v1/project_set_files"

    # get email and project id from .colabond/colabond.yaml
    with open(".colabond/colabond.yaml", "r") as f:
        y = yaml.load(f, yaml.FullLoader)
    project_id = y["project_id"]
    email = y["email"]

    # send .colabond/files.tar.gz
    data = {
        "project_id": project_id,
        "files": files,
        "email": email,
    }
    r = requests.post(url, data=data)
    if r.json()["status"] == "error":
        print(termcolor.colored(r.json()["message"], "red"))
        sys.exit(1)
    print("Full sync completed")


@require_auth
def interactive():
    """Run the interactive shell"""
    print(BANNER)
    while True:
        print(PROMPT)

        command_to_send = input()

        # Local commands
        if command_to_send.strip() == "":
            continue
        elif command_to_send == "exit":
            break
        elif command_to_send == "full-sync":
            full_sync()
        elif command_to_send == "clear":
            os.system("clear")
            print(BANNER)
        else:
            exec(command_to_send)


def main():
    args = sys.argv

    if len(args) < 2:
        display_help()
        sys.exit(1)

    command = args[1]

    if command == "connect":
        connect()
        print("Project connected")
        full_sync()
        print("Initial full sync completed")
    elif command == "signin":
        signin()
    elif command == "signout":
        signout()
    elif command == "full-sync":
        full_sync()
    elif command == "exec":
        if len(sys.argv) > 2:
            if sys.argv[2] in ["-i", "--interactive"]:
                interactive()
            else:
                exec(" ".join(sys.argv[2:]))
        else:
            print("Error: 'exec' must be followed by a command")
            sys.exit(1)

    else:
        print("Unknown command: {}".format(command))
        print()
        display_help()
        sys.exit(1)
