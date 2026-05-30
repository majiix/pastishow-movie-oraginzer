import os
import sys
import subprocess

def run_build():
    print("=== Movie Organizer Executable Builder ===")
    
    # 1. Install pyinstaller if not already installed
    try:
        import PyInstaller
        print(f"PyInstaller version {PyInstaller.__version__} is already installed.")
    except ImportError:
        print("PyInstaller is not installed. Installing via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            import PyInstaller
            print(f"PyInstaller successfully installed: {PyInstaller.__version__}")
        except Exception as e:
            print(f"Failed to install PyInstaller: {e}")
            sys.exit(1)
            
    # 2. Get CustomTkinter directory to bundle its assets
    try:
        import customtkinter
        ctk_dir = os.path.dirname(customtkinter.__file__)
        print(f"CustomTkinter directory found: {ctk_dir}")
    except ImportError:
        print("CustomTkinter is not installed. Please install it first.")
        sys.exit(1)
        
    # 3. Formulate PyInstaller command
    # We package main.py as a single file, with no console window, adding customtkinter assets and custom icon
    sep = os.pathsep # ';' on Windows, ':' on Unix
    add_data_arg = f"--add-data={ctk_dir}{sep}customtkinter"
    
    icon_arg = []
    icon_data_args = []
    if os.path.exists("app_icon.ico"):
        icon_arg = ["--icon=app_icon.ico"]
        icon_data_args.append(f"--add-data=app_icon.ico{sep}.")
    if os.path.exists("app_icon.png"):
        icon_data_args.append(f"--add-data=app_icon.png{sep}.")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--clean"
    ] + icon_arg + icon_data_args + [
        add_data_arg,
        "--name=MovieOrganizer",
        "main.py"
    ]
    
    print(f"\nRunning Build Command:\n{' '.join(cmd)}\n")
    
    try:
        # Run PyInstaller
        subprocess.check_call(cmd)
        print("\nBuild Successful!")
        exe_name = "MovieOrganizer.exe" if sys.platform.startswith("win") else "MovieOrganizer"
        exe_path = os.path.abspath(os.path.join("dist", exe_name))
        print(f"Executable is located at:\n{exe_path}")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    run_build()
