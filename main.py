import sys
import os
from gui import MovieOrganizerApp

def main():
    # If a path was passed via command line (Explorer context menu), check it
    start_path = None
    if len(sys.argv) > 1:
        # Check if the arg is a directory
        potential_path = sys.argv[1]
        if os.path.isdir(potential_path):
            start_path = potential_path
            
    # Start the app
    app = MovieOrganizerApp(start_path)
    app.mainloop()

if __name__ == "__main__":
    main()
