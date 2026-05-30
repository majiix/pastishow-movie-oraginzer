import os
import re
import json
import ssl
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

__version__ = "1.0.0"

# Extensions categorized
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.sub', '.idx', '.vtt', '.ssa'}
INFO_EXTENSIONS = {'.nfo', '.txt', '.jpg', '.jpeg', '.png', '.gif'}
ALL_ASSOCIATED_EXTENSIONS = SUBTITLE_EXTENSIONS.union(INFO_EXTENSIONS)

# Common words to split on if no year is found
QUALITY_KEYWORDS = [
    r'1080p', r'720p', r'2160p', r'4k', r'8k', r'3d',
    r'bluray', r'brrip', r'bdrip', r'dvdrip', r'webrip', r'web-dl', r'web', r'hdrip', r'hdtv',
    r'x264', r'x265', r'h264', r'h265', r'hevc',
    r'aac', r'dts', r'dd5\.1', r'ac3', r'eac3', r'atmos',
    r'yts', r'yify', r'rarbg', r'psa', r'qxr', r'galaxyrg', r'tigole', r'fgt', r'spark',
    r'dual[\s\.-]audio', r'multi[\s\.-]audio', r'multi', r'dubbed', r'subbed',
    r'season', r's\d{2}e\d{2}', r's\d{2}'
]

class MovieOrganizer:
    def __init__(self, target_dir, enable_debug_log=True):
        self.target_dir = os.path.abspath(target_dir)
        self.enable_debug_log = enable_debug_log
        self.connection_failed = False

    def _log_debug(self, message):
        if getattr(self, 'enable_debug_log', True):
            try:
                debug_file = os.path.join(self.target_dir, '.organizer_debug.log')
                with open(debug_file, 'a', encoding='utf-8') as f_dbg:
                    f_dbg.write(message + "\n")
            except Exception:
                pass

    def clean_name(self, filename):
        """
        Parses a movie filename to extract the movie title and the release year.
        Returns a tuple: (title, year) where year can be None.
        """
        # Get base name without extension
        base_name, _ = os.path.splitext(filename)
        
        # 1. Search for a 4-digit year (1900 to 2099) surrounded by boundaries/punctuation
        # Match e.g. "Movie.Name.2020.1080p..." or "Movie Name (2020)" or "Movie Name [2020]"
        year_match = re.search(r'(?:\b|[\(\[\._-])(19\d{2}|20\d{2})(?:\b|[\)\]\._-])', base_name)
        
        title_part = base_name
        year = None
        
        if year_match:
            year = year_match.group(1)
            # Split filename at the start of the year match
            title_part = base_name[:year_match.start()]
        else:
            # 2. If no year is found, look for quality/release keywords to truncate the name
            # Compile regex of keywords
            kw_pattern = '|'.join(QUALITY_KEYWORDS)
            kw_match = re.search(rf'(?:\b|[\(\[\._-])({kw_pattern})(?:\b|[\)\]\._-])', base_name, re.IGNORECASE)
            if kw_match:
                title_part = base_name[:kw_match.start()]

        # Clean the title part
        # Replace common delimiters with spaces
        title = re.sub(r'[\._\-\(\)\[\]\{\}\+]', ' ', title_part)
        
        # Replace multiple spaces with a single space
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Title casing (e.g. "the matrix" -> "The Matrix")
        # Keep capital letters that were already capital (e.g. "iPad", "MCU") but capitalize lowercase word starts
        title = ' '.join(word.capitalize() if word.islower() else word for word in title.split())
        
        # Handle empty title corner cases
        if not title:
            title = base_name
            
        return title, year

    def scan_movies(self, min_size_mb=150, scan_subfolders=False, api_key=None, proxy_url=None):
        """
        Scans the target directory for movies.
        Returns a tuple: (movies_list, ignored_count)
        """
        self.connection_failed = False
        min_size_bytes = min_size_mb * 1024 * 1024
        movies = []
        ignored_count = 0
        
        # Gather all files in target folder
        all_files = []
        if scan_subfolders:
            for root, _, files in os.walk(self.target_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, self.target_dir)
                    all_files.append(rel_path)
        else:
            for f in os.listdir(self.target_dir):
                if os.path.isfile(os.path.join(self.target_dir, f)):
                    all_files.append(f)

        # Filter and process video files
        for rel_path in all_files:
            full_path = os.path.join(self.target_dir, rel_path)
            _, ext = os.path.splitext(rel_path)
            ext = ext.lower()
            
            if ext in VIDEO_EXTENSIONS:
                try:
                    size_bytes = os.path.getsize(full_path)
                except OSError:
                    continue
                    
                if size_bytes >= min_size_bytes:
                    filename = os.path.basename(rel_path)
                    title, year = self.clean_name(filename)
                    
                    # Find associated files
                    # Associated files are in the same folder as the video file and start with the same name root
                    video_dir = os.path.dirname(full_path)
                    video_base, _ = os.path.splitext(filename)
                    
                    associated = []
                    try:
                        for sibling in os.listdir(video_dir):
                            sibling_full = os.path.join(video_dir, sibling)
                            if os.path.isfile(sibling_full) and sibling != filename:
                                sibling_base, sibling_ext = os.path.splitext(sibling)
                                sibling_ext = sibling_ext.lower()
                                
                                # Check if it starts with the video base name (e.g. Inception.2010.en.srt starts with Inception.2010)
                                # And is an allowed associated file extension
                                if sibling_base.startswith(video_base) and sibling_ext in ALL_ASSOCIATED_EXTENSIONS:
                                    # Store relative path to target_dir
                                    sib_rel = os.path.relpath(sibling_full, self.target_dir)
                                    associated.append(sib_rel)
                    except OSError:
                        pass

                    movies.append({
                        'original_filename': filename,
                        'original_relative_path': rel_path,
                        'size_mb': round(size_bytes / (1024 * 1024), 1),
                        'parsed_title': title,
                        'parsed_year': year,
                        'associated_files': associated
                    })
                else:
                    ignored_count += 1
                    
        sorted_movies = sorted(movies, key=lambda m: m['parsed_title'])
        
        # Detect TV shows based on parsed title frequencies
        from collections import Counter
        title_counts = Counter(m['parsed_title'].lower().strip() for m in sorted_movies)
        for m in sorted_movies:
            t = m['parsed_title'].lower().strip()
            m['is_tv_show'] = title_counts[t] > 1
        
        # Concurrent fetching of IMDb ratings if API key is provided
        if api_key and sorted_movies:
            from concurrent.futures import ThreadPoolExecutor
            
            ssl_context = ssl._create_unverified_context()
            
            # Setup custom opener handlers to route through proxy
            handlers = [urllib.request.HTTPSHandler(context=ssl_context), urllib.request.HTTPHandler]
            if proxy_url:
                if proxy_url.lower() == 'none':
                    # Explicitly disable proxies (bypasses broken system settings)
                    handlers.append(urllib.request.ProxyHandler({}))
                else:
                    handlers.append(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))
            
            opener = urllib.request.build_opener(*handlers)
            
            def fetch_rating(movie):
                title = movie['parsed_title']
                is_tv = movie.get('is_tv_show', False)
                try:
                    year = movie['parsed_year']
                    data = None
                    
                    # 1. Try with title and year first (HTTPS preferred)
                    if year and year.strip():
                        params = {'t': title, 'y': year.strip(), 'apikey': api_key}
                        if is_tv:
                            params['type'] = 'series'
                        url = "https://www.omdbapi.com/?" + urllib.parse.urlencode(params)
                        req = urllib.request.Request(url, headers={'User-Agent': 'MovieOrganizer/1.0'})
                        try:
                            with opener.open(req, timeout=3.0) as response:
                                data = json.loads(response.read().decode('utf-8'))
                        except Exception as e_inner:
                            self._log_debug(f"Inner OMDb search failed for '{title}' (year {year}): {e_inner}")
                            if isinstance(e_inner, urllib.error.URLError) or "timeout" in str(e_inner).lower() or "connection" in str(e_inner).lower():
                                self.connection_failed = True
                    
                    # 2. Fallback to title-only if first search failed or wasn't attempted
                    if not data or data.get('Response') != 'True':
                        params = {'t': title, 'apikey': api_key}
                        if is_tv:
                            params['type'] = 'series'
                        url = "https://www.omdbapi.com/?" + urllib.parse.urlencode(params)
                        req = urllib.request.Request(url, headers={'User-Agent': 'MovieOrganizer/1.0'})
                        with opener.open(req, timeout=3.0) as response:
                            data = json.loads(response.read().decode('utf-8'))
                            
                    # Process response
                    if data and data.get('Response') == 'True':
                        rating = data.get('imdbRating')
                        poster = data.get('Poster')
                        genre = data.get('Genre')
                        
                        movie['omdb_data'] = data
                        if rating and rating != 'N/A':
                            movie['imdb_rating'] = rating
                        if poster and poster != 'N/A' and poster.startswith('http'):
                            movie['poster_url'] = poster
                        if genre and genre != 'N/A':
                            movie['genre'] = genre
                    else:
                        err_msg = data.get('Error', 'Unknown Error') if data else 'No response data'
                        self._log_debug(f"OMDb match failed for '{title}': {err_msg}")
                except Exception as e:
                    self._log_debug(f"OMDb connection/general error for '{title}': {e}")
                    if isinstance(e, urllib.error.URLError) or "timeout" in str(e).lower() or "connection" in str(e).lower():
                        self.connection_failed = True
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(fetch_rating, sorted_movies))
                
        return sorted_movies, ignored_count

    def organize_movies(self, selections, naming_pattern="{title} ({year})", api_key=None, proxy_url=None):
        """
        Organizes the selected movies.
        selections: list of dicts from scan_movies with modifications:
        [
            {
                'original_relative_path': 'Inception.2010.mp4',
                'parsed_title': 'Inception',
                'parsed_year': '2010',
                'associated_files': ['Inception.2010.srt']
            }
        ]
        """
        self.connection_failed = False
        import struct
        
        ssl_context = ssl._create_unverified_context()
        
        # Setup custom opener handlers to route through proxy
        handlers = [urllib.request.HTTPSHandler(context=ssl_context), urllib.request.HTTPHandler]
        if proxy_url:
            if proxy_url.lower() == 'none':
                # Explicitly disable proxies (bypasses broken system settings)
                handlers.append(urllib.request.ProxyHandler({}))
            else:
                handlers.append(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))
        
        opener = urllib.request.build_opener(*handlers)
        
        moves_performed = []
        created_dirs = set()
        
        for item in selections:
            title = item['parsed_title'].strip()
            year = item['parsed_year']
            rating = item.get('imdb_rating')
            poster_url = item.get('poster_url')
            genre = item.get('genre')
            is_tv = item.get('is_tv_show', False)
            
            # Fetch rating/poster/genre on the fly if missing and api_key is available
            if api_key and (not rating or not poster_url or not genre):
                try:
                    data = None
                    # Try with year first (HTTPS preferred)
                    if year and year.strip():
                        params = {'t': title, 'y': year.strip(), 'apikey': api_key}
                        if is_tv:
                            params['type'] = 'series'
                        url = "https://www.omdbapi.com/?" + urllib.parse.urlencode(params)
                        req = urllib.request.Request(url, headers={'User-Agent': 'MovieOrganizer/1.0'})
                        try:
                            with opener.open(req, timeout=3.0) as response:
                                data = json.loads(response.read().decode('utf-8'))
                        except Exception as e_inner:
                            if isinstance(e_inner, urllib.error.URLError) or "timeout" in str(e_inner).lower() or "connection" in str(e_inner).lower():
                                self.connection_failed = True
                            
                    # Fallback to title-only
                    if not data or data.get('Response') != 'True':
                        params = {'t': title, 'apikey': api_key}
                        if is_tv:
                            params['type'] = 'series'
                        url = "https://www.omdbapi.com/?" + urllib.parse.urlencode(params)
                        req = urllib.request.Request(url, headers={'User-Agent': 'MovieOrganizer/1.0'})
                        try:
                            with opener.open(req, timeout=3.0) as response:
                                data = json.loads(response.read().decode('utf-8'))
                        except Exception as e_inner:
                            if isinstance(e_inner, urllib.error.URLError) or "timeout" in str(e_inner).lower() or "connection" in str(e_inner).lower():
                                self.connection_failed = True
                            
                    if data and data.get('Response') == 'True':
                        item['omdb_data'] = data
                        if not rating:
                            rating = data.get('imdbRating')
                            if rating == 'N/A':
                                rating = None
                            else:
                                item['imdb_rating'] = rating
                        if not poster_url:
                            poster_url = data.get('Poster')
                            if poster_url == 'N/A':
                                poster_url = None
                            else:
                                item['poster_url'] = poster_url
                        if not genre:
                            genre = data.get('Genre')
                            if genre == 'N/A':
                                genre = None
                            else:
                                item['genre'] = genre
                except Exception as e:
                    if isinstance(e, urllib.error.URLError) or "timeout" in str(e).lower() or "connection" in str(e).lower():
                        self.connection_failed = True
            
            # Sanitize title for directory name (remove Windows invalid characters: \ / : * ? " < > |)
            dir_title = re.sub(r'[\\/:*?"<>|]', '', title)
            
            # Format folder name parts
            folder_parts = []
            if year and year.strip():
                folder_parts.append(f"{dir_title} ({year.strip()})")
            else:
                folder_parts.append(dir_title)
                
            if rating and rating.strip():
                folder_parts.append(f"[{rating.strip()}]")
                
            if genre and genre.strip():
                clean_genre = re.sub(r'[\\/:*?"<>|]', '', genre.strip())
                folder_parts.append(f"[{clean_genre}]")
                
            folder_name = " ".join(folder_parts).strip()
            
            # Determine files to move: video file + associated files
            files_to_move = [item['original_relative_path']] + item.get('associated_files', [])
            
            # Check if film is already inside a subfolder
            sub_dir_rel = os.path.dirname(item['original_relative_path'])
            
            if sub_dir_rel:
                # It's inside a subfolder. Rename that subfolder in-place!
                src_dir_full = os.path.abspath(os.path.join(self.target_dir, sub_dir_rel))
                parent_dir = os.path.dirname(src_dir_full)
                dest_dir_full = os.path.abspath(os.path.join(parent_dir, folder_name))
                
                # Check for conflicts
                if src_dir_full != dest_dir_full:
                    if os.path.exists(dest_dir_full):
                        counter = 1
                        base_folder_name = folder_name
                        while os.path.exists(os.path.join(parent_dir, f"{base_folder_name}_{counter}")):
                            counter += 1
                        folder_name = f"{base_folder_name}_{counter}"
                        dest_dir_full = os.path.abspath(os.path.join(parent_dir, folder_name))
                        
                    try:
                        os.rename(src_dir_full, dest_dir_full)
                        created_rel = os.path.relpath(dest_dir_full, self.target_dir)
                        created_dirs.add(created_rel)
                        
                        # Record moves for undo (map each old relative file path to the new relative path)
                        for rel_file in files_to_move:
                            # Calculate relative path inside directory to handle nested files correctly
                            rel_inside_sub = os.path.relpath(os.path.join(self.target_dir, rel_file), src_dir_full)
                            new_file_full = os.path.join(dest_dir_full, rel_inside_sub)
                            new_file_rel = os.path.relpath(new_file_full, self.target_dir)
                            
                            moves_performed.append({
                                'original_relative_path': rel_file,
                                'new_relative_path': new_file_rel
                            })
                    except OSError as e:
                        print(f"Error renaming directory {src_dir_full} to {dest_dir_full}: {e}")
            else:
                # Normal move logic (it's at the root)
                dest_dir_full = os.path.abspath(os.path.join(self.target_dir, folder_name))
                
                # Create folder if it doesn't exist
                if not os.path.exists(dest_dir_full):
                    os.makedirs(dest_dir_full, exist_ok=True)
                    created_dirs.add(folder_name)
                    
                for rel_file in files_to_move:
                    src_full = os.path.join(self.target_dir, rel_file)
                    if os.path.exists(src_full):
                        filename = os.path.basename(rel_file)
                        dest_full = os.path.join(dest_dir_full, filename)
                        
                        # Prevent overwriting if file already exists in destination
                        if src_full != dest_full:
                            if os.path.exists(dest_full):
                                # Append a suffix if there is a conflict
                                base, ext = os.path.splitext(filename)
                                counter = 1
                                while os.path.exists(os.path.join(dest_dir_full, f"{base}_{counter}{ext}")):
                                    counter += 1
                                dest_full = os.path.join(dest_dir_full, f"{base}_{counter}{ext}")
                            
                            # Perform move
                            try:
                                os.rename(src_full, dest_full)
                                dest_rel = os.path.relpath(dest_full, self.target_dir)
                                moves_performed.append({
                                    'original_relative_path': rel_file,
                                    'new_relative_path': dest_rel
                                })
                            except OSError as e:
                                print(f"Error moving {rel_file}: {e}")
            
            # Download poster if poster_url is available and not already downloaded
            poster_url = item.get('poster_url') or poster_url
            if poster_url:
                poster_dest = os.path.join(dest_dir_full, "poster.jpg")
                if not os.path.exists(poster_dest):
                    try:
                        req = urllib.request.Request(poster_url, headers={'User-Agent': 'MovieOrganizer/1.0'})
                        with opener.open(req, timeout=5.0) as response:
                            poster_data = response.read()
                            with open(poster_dest, "wb") as f_img:
                                f_img.write(poster_data)
                            
                            # Record in moves_performed for undo (original_relative_path is None)
                            dest_rel = os.path.relpath(poster_dest, self.target_dir)
                            moves_performed.append({
                                'original_relative_path': None,
                                'new_relative_path': dest_rel
                            })
                    except Exception as e:
                        self._log_debug(f"Poster download failed for '{title}' (URL: {poster_url}): {e}")
                        if isinstance(e, urllib.error.URLError) or "timeout" in str(e).lower() or "connection" in str(e).lower():
                            self.connection_failed = True

            # Create beautiful HTML details page
            if not self.connection_failed:
                try:
                    about_path = self._create_movie_html_page(dest_dir_full, item)
                    if about_path and os.path.exists(about_path):
                        dest_rel = os.path.relpath(about_path, self.target_dir)
                        moves_performed.append({
                            'original_relative_path': None,
                            'new_relative_path': dest_rel
                        })
                except Exception as e:
                    self._log_debug(f"Failed to create HTML page for '{title}': {e}")

        # Save history log if any move succeeded
        if moves_performed:
            history_data = {
                'timestamp': datetime.now().isoformat(),
                'moves': moves_performed,
                'created_folders': list(created_dirs)
            }
            self._save_history(history_data)
            return len(selections)
            
        return 0

    def _save_history(self, history_data):
        history_file = os.path.join(self.target_dir, '.organizer_history.json')
        
        # Load existing history if any
        history_list = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_list = json.load(f)
                    if not isinstance(history_list, list):
                        history_list = []
            except (json.JSONDecodeError, OSError):
                pass
                
        history_list.append(history_data)
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_list, f, indent=4, ensure_ascii=False)
        except OSError as e:
            print(f"Failed to write history file: {e}")

    def undo_last_action(self):
        """
        Reverses the last batch organization operation using `.organizer_history.json`.
        Returns: (success_count, failed_count) or None if no history exists.
        """
        history_file = os.path.join(self.target_dir, '.organizer_history.json')
        if not os.path.exists(history_file):
            return None
            
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_list = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
            
        if not history_list or not isinstance(history_list, list):
            return None
            
        # Get the last operation
        last_action = history_list.pop()
        
        moves = last_action.get('moves', [])
        created_folders = last_action.get('created_folders', [])
        
        success_count = 0
        failed_count = 0
        
        # Move files back in reverse order
        for move in reversed(moves):
            src_rel = move['new_relative_path']
            dest_rel = move['original_relative_path']
            
            src_full = os.path.join(self.target_dir, src_rel)
            
            if os.path.exists(src_full):
                if dest_rel:
                    dest_full = os.path.join(self.target_dir, dest_rel)
                    # Ensure original subdirectories exist if they were deleted/moved from
                    dest_dir = os.path.dirname(dest_full)
                    if dest_dir:
                        os.makedirs(dest_dir, exist_ok=True)
                    
                    try:
                        os.rename(src_full, dest_full)
                        success_count += 1
                    except OSError:
                        failed_count += 1
                else:
                    # New file (e.g. poster), delete it
                    try:
                        os.remove(src_full)
                        success_count += 1
                    except OSError:
                        failed_count += 1
            else:
                failed_count += 1
                
        # Clean up empty folders that were created
        for folder in created_folders:
            folder_full = os.path.join(self.target_dir, folder)
            if os.path.exists(folder_full) and os.path.isdir(folder_full):
                # Check if it's empty
                try:
                    if not os.listdir(folder_full):
                        os.rmdir(folder_full)
                except OSError:
                    pass
                    
        # Update history file
        try:
            if history_list:
                with open(history_file, 'w', encoding='utf-8') as f:
                    json.dump(history_list, f, indent=4, ensure_ascii=False)
            else:
                os.remove(history_file)
        except OSError:
            pass
            
        return success_count, failed_count

    def _create_movie_html_page(self, dest_dir_full, item):
        """
        Creates a beautifully styled, high-end about.html page inside the movie's destination folder.
        """
        import html
        
        about_path = os.path.join(dest_dir_full, "about.html")
        title = item.get('parsed_title', '').strip()
        year = item.get('parsed_year', '').strip()
        omdb_data = item.get('omdb_data')
        
        # Check local poster
        poster_local_exists = os.path.exists(os.path.join(dest_dir_full, "poster.jpg"))
        
        # Date & Size details
        size_mb = item.get('size_mb', 'N/A')
        date_str = datetime.now().strftime("%B %d, %Y")
        
        if omdb_data and isinstance(omdb_data, dict) and omdb_data.get('Response') == 'True':
            m_title = omdb_data.get('Title', title)
            m_year = omdb_data.get('Year', year)
            m_rated = omdb_data.get('Rated', 'N/A')
            m_released = omdb_data.get('Released', 'N/A')
            m_runtime = omdb_data.get('Runtime', 'N/A')
            m_genre = omdb_data.get('Genre', 'N/A')
            m_director = omdb_data.get('Director', 'N/A')
            m_writer = omdb_data.get('Writer', 'N/A')
            m_actors = omdb_data.get('Actors', 'N/A')
            m_plot = omdb_data.get('Plot', 'No plot details available.')
            m_language = omdb_data.get('Language', 'N/A')
            m_country = omdb_data.get('Country', 'N/A')
            m_awards = omdb_data.get('Awards', 'N/A')
            m_boxoffice = omdb_data.get('BoxOffice', 'N/A')
            m_imdb_rating = omdb_data.get('imdbRating', 'N/A')
            m_imdb_votes = omdb_data.get('imdbVotes', 'N/A')
            ratings = omdb_data.get('Ratings', [])
            
            # Format genres
            genres = [g.strip() for g in m_genre.split(',')] if m_genre != 'N/A' else []
            genres_html = "".join(f'<span class="genre-tag">{html.escape(g)}</span>' for g in genres)
            
            # Poster source
            if poster_local_exists:
                poster_src_html = '<img src="poster.jpg" alt="Poster" class="poster-img">'
            else:
                poster_url = omdb_data.get('Poster')
                if poster_url and poster_url != 'N/A' and poster_url.startswith('http'):
                    poster_src_html = f'<img src="{html.escape(poster_url)}" alt="Poster" class="poster-img">'
                else:
                    poster_src_html = f'<div class="poster-placeholder"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48" style="margin-bottom: 12px; color: var(--text-muted);"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></svg><div style="font-weight: 600; font-size: 0.95rem; color: var(--text-secondary); text-align: center; padding: 0 16px;">{html.escape(m_title)}</div></div>'
            
            # Ratings formatting
            ratings_html = ""
            for r in ratings:
                r_src = r.get('Source', '')
                r_val = r.get('Value', '')
                if "Internet Movie Database" in r_src:
                    r_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" width="16" height="16" style="vertical-align: middle; margin-right: 8px;"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>'
                    r_name = "IMDb"
                elif "Rotten Tomatoes" in r_src:
                    r_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#ef4444" width="16" height="16" style="vertical-align: middle; margin-right: 8px;"><path d="M12 2c-.55 0-1 .45-1 1v1.1c-3.95.49-7 3.85-7 7.9 0 4.42 3.58 8 8 8s8-3.58 8-8c0-4.05-3.05-7.41-7-7.9V3c0-.55-.45-1-1-1zm0 4.5c2.48 0 4.5 2.02 4.5 4.5S14.48 15.5 12 15.5 7.5 13.48 7.5 11s2.02-4.5 4.5-4.5z"/></svg>'
                    r_name = "Rotten Tomatoes"
                elif "Metacritic" in r_src:
                    r_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#10b981" width="16" height="16" style="vertical-align: middle; margin-right: 8px;"><rect width="20" height="20" x="2" y="2" rx="4" ry="4"/><text x="12" y="16" fill="white" font-size="12" font-weight="bold" text-anchor="middle" font-family="sans-serif">M</text></svg>'
                    r_name = "Metacritic"
                else:
                    r_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#94a3b8" width="16" height="16" style="vertical-align: middle; margin-right: 8px;"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"/></svg>'
                    r_name = r_src
                
                ratings_html += f"""
                <div class="rating-item">
                    <span class="rating-source">{r_icon}{html.escape(r_name)}</span>
                    <span class="rating-value">{html.escape(r_val)}</span>
                </div>
                """
            
            if not ratings_html and m_imdb_rating != 'N/A':
                ratings_html = f"""
                <div class="rating-item">
                    <span class="rating-source">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" width="16" height="16" style="vertical-align: middle; margin-right: 8px;"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
                        IMDb
                    </span>
                    <span class="rating-value">{html.escape(m_imdb_rating)}/10</span>
                </div>
                """
            
            if not ratings_html:
                ratings_html = '<div style="color: var(--text-muted); text-align: center; padding: 10px 0; font-size: 0.9rem;">No ratings details available</div>'
                
            awards_html = ""
            if m_awards and m_awards != 'N/A' and m_awards.strip():
                awards_html = f"""
                <div class="awards-banner">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" width="24" height="24" style="flex-shrink: 0;"><path d="M12 2a10 10 0 0 1 8 16.27V22h-2v-3.73A10 10 0 0 1 12 20a10 10 0 0 1-8-1.73V22H2v-3.73A10 10 0 0 1 12 2zM12 4a8 8 0 0 0-6 2.68c.5.83 1.22 1.5 2.1 2A7.94 7.94 0 0 0 12 6a7.94 7.94 0 0 0 3.9.68 5.76 5.76 0 0 1 2.1-2A8 8 0 0 0 12 4zm0 4a4 4 0 0 0-3 1.34c.5.55 1.13.96 1.83 1.21A3.97 3.97 0 0 0 12 10a3.97 3.97 0 0 0 1.17.55 3.73 3.73 0 0 1 1.83-1.21A4 4 0 0 0 12 8z"/></svg>
                    <span class="awards-text">{html.escape(m_awards)}</span>
                </div>
                """
            
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(m_title)} ({html.escape(m_year)}) | Movie Details</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(20, 27, 45, 0.65);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-color: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.12);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --imdb-gold: #f59e0b;
        }}
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: var(--bg-color);
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--card-border);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}
        
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }}
        
        body::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 20%;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.06) 0%, rgba(0, 0, 0, 0) 70%);
            z-index: 0;
            pointer-events: none;
        }}
        
        body::after {{
            content: '';
            position: absolute;
            bottom: 0;
            right: 10%;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(139, 92, 246, 0.05) 0%, rgba(0, 0, 0, 0) 70%);
            z-index: 0;
            pointer-events: none;
        }}
        
        .container {{
            position: relative;
            z-index: 1;
            width: 90%;
            max-width: 1000px;
            margin: 40px auto;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 24px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            padding: 40px;
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 40px;
            transition: all 0.3s ease;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                grid-template-columns: 1fr;
                padding: 24px;
                gap: 24px;
                margin: 20px auto;
            }}
        }}
        
        .left-col {{
            display: flex;
            flex-direction: column;
            gap: 24px;
            align-items: center;
        }}
        
        .poster-wrapper {{
            width: 100%;
            max-width: 300px;
            aspect-ratio: 2/3;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.4s cubic-bezier(0.165, 0.84, 0.44, 1), box-shadow 0.4s ease;
        }}
        
        .poster-wrapper:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 35px rgba(56, 189, 248, 0.2);
        }}
        
        .poster-img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }}
        
        .poster-placeholder {{
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            aspect-ratio: 2/3;
            border-radius: 16px;
            border: 1px dashed rgba(255, 255, 255, 0.1);
        }}
        
        .ratings-box {{
            width: 100%;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            padding: 16px;
        }}
        
        .rating-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .rating-item:last-child {{
            border-bottom: none;
            padding-bottom: 0;
        }}
        
        .rating-item:first-child {{
            padding-top: 0;
        }}
        
        .rating-source {{
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
        }}
        
        .rating-value {{
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-primary);
            padding: 4px 8px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
        }}
        
        .right-col {{
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}
        
        .movie-header {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        
        .movie-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 800;
            line-height: 1.2;
            margin: 0;
            background: linear-gradient(135deg, #ffffff 40%, #93c5fd 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .movie-meta-strip {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}
        
        .meta-badge {{
            background: rgba(255, 255, 255, 0.06);
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .genre-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 4px;
        }}
        
        .genre-tag {{
            background: var(--accent-glow);
            color: var(--accent-color);
            border: 1px solid rgba(56, 189, 248, 0.25);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }}
        
        .genre-tag:hover {{
            background: rgba(56, 189, 248, 0.22);
            transform: translateY(-2px);
        }}
        
        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-color);
            margin: 0 0 10px 0;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        
        .plot-box {{
            font-size: 1.05rem;
            line-height: 1.7;
            color: #e2e8f0;
            margin: 0;
        }}
        
        .people-grid {{
            display: flex;
            flex-direction: column;
            gap: 14px;
            background: rgba(255, 255, 255, 0.01);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 16px;
            padding: 20px;
        }}
        
        .people-item {{
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 12px;
            font-size: 0.95rem;
            line-height: 1.5;
        }}
        
        @media (max-width: 480px) {{
            .people-item {{
                grid-template-columns: 1fr;
                gap: 4px;
            }}
        }}
        
        .people-role {{
            font-weight: 600;
            color: var(--text-secondary);
        }}
        
        .people-names {{
            color: var(--text-primary);
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }}
        
        .info-card {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 14px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        .info-card:hover {{
            border-color: rgba(56, 189, 248, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
        }}
        
        .info-label {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        
        .info-value {{
            font-size: 0.95rem;
            font-weight: 500;
            color: var(--text-primary);
            word-break: break-word;
            overflow-wrap: break-word;
        }}
        
        .awards-banner {{
            display: flex;
            align-items: center;
            gap: 16px;
            background: linear-gradient(90deg, rgba(245, 158, 11, 0.08) 0%, rgba(0, 0, 0, 0) 100%);
            border-left: 4px solid var(--imdb-gold);
            border-radius: 4px 12px 12px 4px;
            padding: 16px 20px;
        }}
        
        .awards-text {{
            font-size: 0.95rem;
            color: #fef3c7;
            font-weight: 500;
        }}
        
        .footer {{
            margin-top: 10px;
            text-align: center;
            font-size: 0.75rem;
            color: var(--text-muted);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="left-col">
            <div class="poster-wrapper">
                {poster_src_html}
            </div>
            
            <div class="ratings-box">
                <div class="section-title" style="font-size: 0.9rem; text-align: center; margin-bottom: 12px;">Ratings</div>
                {ratings_html}
            </div>
        </div>
        
        <div class="right-col">
            <div class="movie-header">
                <h1 class="movie-title">{html.escape(m_title)}</h1>
                <div class="movie-meta-strip">
                    <span class="meta-badge">{html.escape(m_rated)}</span>
                    <span>{html.escape(m_released)}</span>
                    <span>&bull;</span>
                    <span>{html.escape(m_runtime)}</span>
                </div>
                
                <div class="genre-tags">
                    {genres_html}
                </div>
            </div>
            
            {awards_html}
            
            <div class="plot-section">
                <div class="section-title">Plot Summary</div>
                <p class="plot-box">{html.escape(m_plot)}</p>
            </div>
            
            <div class="cast-section">
                <div class="section-title">Cast & Crew</div>
                <div class="people-grid">
                    <div class="people-item">
                        <span class="people-role">Director</span>
                        <span class="people-names">{html.escape(m_director)}</span>
                    </div>
                    <div class="people-item">
                        <span class="people-role">Writer</span>
                        <span class="people-names">{html.escape(m_writer)}</span>
                    </div>
                    <div class="people-item">
                        <span class="people-role">Actors</span>
                        <span class="people-names">{html.escape(m_actors)}</span>
                    </div>
                </div>
            </div>
            
            <div class="details-section">
                <div class="section-title">Additional Info</div>
                <div class="info-grid">
                    <div class="info-card">
                        <div class="info-label">Country</div>
                        <div class="info-value">{html.escape(m_country)}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Language</div>
                        <div class="info-value">{html.escape(m_language)}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Box Office</div>
                        <div class="info-value">{html.escape(m_boxoffice)}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">File Size</div>
                        <div class="info-value">{html.escape(str(size_mb))} MB</div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                Organized on {html.escape(date_str)} by Movie Organizer
            </div>
        </div>
    </div>
</body>
</html>"""
        else:
            # Fallback version for when we do not have OMDb metadata
            m_title = title
            m_year = year if year else 'Unknown Year'
            m_plot = "Metadata details were not retrieved from OMDb. Connect an OMDb API Key in the application settings to automatically download movie cover posters, cast, crew, ratings, plot details, and other cinematic info!"
            
            poster_src_html = f'<div class="poster-placeholder"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48" style="margin-bottom: 12px; color: var(--text-muted);"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></svg><div style="font-weight: 600; font-size: 0.95rem; color: var(--text-secondary); text-align: center; padding: 0 16px;">{html.escape(m_title)}</div></div>'
            
            ratings_html = '<div style="color: var(--text-muted); text-align: center; padding: 10px 0; font-size: 0.9rem;">No ratings details available</div>'
            
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(m_title)} ({html.escape(m_year)}) | Movie Details</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(20, 27, 45, 0.65);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-color: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.12);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
        }}
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: var(--bg-color);
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--card-border);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}
        
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }}
        
        body::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 20%;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.06) 0%, rgba(0, 0, 0, 0) 70%);
            z-index: 0;
            pointer-events: none;
        }}
        
        body::after {{
            content: '';
            position: absolute;
            bottom: 0;
            right: 10%;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(139, 92, 246, 0.05) 0%, rgba(0, 0, 0, 0) 70%);
            z-index: 0;
            pointer-events: none;
        }}
        
        .container {{
            position: relative;
            z-index: 1;
            width: 90%;
            max-width: 1000px;
            margin: 40px auto;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 24px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            padding: 40px;
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 40px;
            transition: all 0.3s ease;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                grid-template-columns: 1fr;
                padding: 24px;
                gap: 24px;
                margin: 20px auto;
            }}
        }}
        
        .left-col {{
            display: flex;
            flex-direction: column;
            gap: 24px;
            align-items: center;
        }}
        
        .poster-wrapper {{
            width: 100%;
            max-width: 300px;
            aspect-ratio: 2/3;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.4s cubic-bezier(0.165, 0.84, 0.44, 1), box-shadow 0.4s ease;
        }}
        
        .poster-wrapper:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 35px rgba(56, 189, 248, 0.2);
        }}
        
        .poster-placeholder {{
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            aspect-ratio: 2/3;
            border-radius: 16px;
            border: 1px dashed rgba(255, 255, 255, 0.1);
        }}
        
        .ratings-box {{
            width: 100%;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            padding: 16px;
        }}
        
        .right-col {{
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}
        
        .movie-header {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        
        .movie-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 800;
            line-height: 1.2;
            margin: 0;
            background: linear-gradient(135deg, #ffffff 40%, #93c5fd 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .movie-meta-strip {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}
        
        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-color);
            margin: 0 0 10px 0;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        
        .plot-box {{
            font-size: 1.05rem;
            line-height: 1.7;
            color: #e2e8f0;
            margin: 0;
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }}
        
        .info-card {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 14px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        .info-card:hover {{
            border-color: rgba(56, 189, 248, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
        }}
        
        .info-label {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        
        .info-value {{
            font-size: 0.95rem;
            font-weight: 500;
            color: var(--text-primary);
            word-break: break-word;
            overflow-wrap: break-word;
        }}
        
        .footer {{
            margin-top: 10px;
            text-align: center;
            font-size: 0.75rem;
            color: var(--text-muted);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="left-col">
            <div class="poster-wrapper">
                {poster_src_html}
            </div>
            
            <div class="ratings-box">
                <div class="section-title" style="font-size: 0.9rem; text-align: center; margin-bottom: 12px;">Ratings</div>
                {ratings_html}
            </div>
        </div>
        
        <div class="right-col">
            <div class="movie-header">
                <h1 class="movie-title">{html.escape(m_title)}</h1>
                <div class="movie-meta-strip">
                    <span>{html.escape(m_year)}</span>
                </div>
            </div>
            
            <div class="plot-section">
                <div class="section-title">Details</div>
                <p class="plot-box">{html.escape(m_plot)}</p>
            </div>
            
            <div class="details-section">
                <div class="section-title">Additional Info</div>
                <div class="info-grid">
                    <div class="info-card">
                        <div class="info-label">File Size</div>
                        <div class="info-value">{html.escape(str(size_mb))} MB</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Organized On</div>
                        <div class="info-value">{html.escape(date_str)}</div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                Organized on {html.escape(date_str)} by Movie Organizer
            </div>
        </div>
    </div>
</body>
</html>"""
        
        with open(about_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return about_path
