import os
import shutil
import tempfile
from organizer import MovieOrganizer

def run_tests():
    print("=== Starting Movie Organizer Core Tests ===")
    
    # 1. Test Name Parser
    organizer = MovieOrganizer(".")
    
    test_cases = [
        ("Inception.2010.1080p.BluRay.x264.YIFY.mp4", ("Inception", "2010")),
        ("The.Matrix.1999.REMASTERED.mkv", ("The Matrix", "1999")),
        ("Interstellar.2014.2160p.UHD.BluRay.x265.10bit.HDR.DTS-HD.MA.7.1-CTR.mkv", ("Interstellar", "2014")),
        ("Spider-Man.Into.the.Spider-Verse.2018.1080p.mp4", ("Spider Man Into The Spider Verse", "2018")),
        ("Gladiator.Extended.Edition.2000.1080p.BrRip.x264.YIFY.mp4", ("Gladiator Extended Edition", "2000")),
        ("NoYearMovie.1080p.WEBRip.mp4", ("NoYearMovie", None)),
        ("Some.Movie.With.Strange.Name-PSA.mkv", ("Some Movie With Strange Name", None)),
        ("Avatar.The.Way.of.Water.2022.2160p.WEB-DL.DDP5.1.Atmos.H.264.mkv", ("Avatar The Way Of Water", "2022"))
    ]
    
    print("\nTesting Name Cleaning Regex:")
    all_passed = True
    for filename, expected in test_cases:
        title, year = organizer.clean_name(filename)
        status = "PASS" if (title, year) == expected else "FAIL"
        print(f"  {filename:75} -> Title: {title:<30} Year: {str(year):<6} | {status}")
        if (title, year) != expected:
            all_passed = False
            print(f"    Expected: Title: '{expected[0]}' Year: '{expected[1]}'")
            
    assert all_passed, "Name cleaning tests failed!"
    print("Name cleaning tests: PASSED")
    
    # 2. Test File Operations (Scan, Move, Undo)
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="organizer_test_")
    print(f"\nCreated temp directory for file operations testing: {temp_dir}")
    
    try:
        # Create test dummy files
        dummy_files = [
            "Inception.2010.1080p.mp4",
            "Inception.2010.1080p.srt",
            "Inception.2010.1080p.en.srt",
            "The.Matrix.1999.mkv",
            "The.Matrix.1999.srt",
            "The.Matrix.1999.nfo",
            "UnrelatedFile.txt",
            "small_sample.mp4" # We will test size filters
        ]
        
        for f in dummy_files:
            file_path = os.path.join(temp_dir, f)
            with open(file_path, "w") as dummy_f:
                if f == "small_sample.mp4":
                    dummy_f.write("small")
                else:
                    # Write some dummy bytes
                    dummy_f.write("A" * 100) # dummy content
                    
        # Write larger content for size testing
        # Let's say we write 1024 bytes (1KB) and use size threshold in bytes for testing
        # Wait, scan_movies takes size in MB. Let's make it 0 to scan everything including 0-byte files,
        # and test with 1MB to filter small_sample.
        
        # Instantiate organizer on temp dir
        temp_organizer = MovieOrganizer(temp_dir)
        
        # Test scan with min_size = 0 (should detect all videos except unrelated text)
        print("\nScanning temp folder (min_size_mb=0):")
        movies, _ = temp_organizer.scan_movies(min_size_mb=0)
        for m in movies:
            print(f"  Detected: {m['original_filename']} | Title: {m['parsed_title']} | Year: {m['parsed_year']} | Associated count: {len(m['associated_files'])}")
            
        detected_names = {m['original_filename'] for m in movies}
        assert "Inception.2010.1080p.mp4" in detected_names, "Inception not detected"
        assert "The.Matrix.1999.mkv" in detected_names, "Matrix not detected"
        assert "small_sample.mp4" in detected_names, "small_sample not detected"
        assert "UnrelatedFile.txt" not in detected_names, "unrelated text file detected as movie"
        
        # Verify associated files
        inception_entry = next(m for m in movies if m['original_filename'] == "Inception.2010.1080p.mp4")
        assert len(inception_entry['associated_files']) == 2, "Inception subtitles not grouped correctly"
        assert "Inception.2010.1080p.srt" in inception_entry['associated_files'], "srt subtitle missing"
        assert "Inception.2010.1080p.en.srt" in inception_entry['associated_files'], "en.srt subtitle missing"
        
        matrix_entry = next(m for m in movies if m['original_filename'] == "The.Matrix.1999.mkv")
        assert len(matrix_entry['associated_files']) == 2, "Matrix associated files not grouped correctly"
        
        # Test scan with min_size filter
        # We can't write 150MB easily in a fast test, but we can verify our size check logic.
        # Since small_sample.mp4 is 5 bytes, and others are 100 bytes:
        # We will write a test checking the filtering of size.
        # In actual scanner, the size is checked. The 100 bytes movies will be excluded if min_size_mb > 0.
        # Let's verify min_size filtering works:
        movies_filtered, _ = temp_organizer.scan_movies(min_size_mb=10) # 10MB threshold, 100 bytes files should be filtered out
        assert len(movies_filtered) == 0, "Size filter did not exclude small files"
        print("Size filter: PASSED")

        # 3. Test Organization
        print("\nRunning Organization:")
        # We will select Inception and Matrix for organization
        to_organize = [m for m in movies if m['original_filename'] in ("Inception.2010.1080p.mp4", "The.Matrix.1999.mkv")]
        
        organized_count = temp_organizer.organize_movies(to_organize)
        print(f"  Organized {organized_count} movies.")
        assert organized_count == 2, "Failed to organize movies"
        
        # Verify folder structure
        inception_dir = os.path.join(temp_dir, "Inception (2010)")
        matrix_dir = os.path.join(temp_dir, "The Matrix (1999)")
        
        assert os.path.exists(inception_dir) and os.path.isdir(inception_dir), "Inception folder not created"
        assert os.path.exists(matrix_dir) and os.path.isdir(matrix_dir), "Matrix folder not created"
        
        # Check files inside Inception folder
        inception_files = os.listdir(inception_dir)
        print(f"  Inception folder contents: {inception_files}")
        assert "Inception.2010.1080p.mp4" in inception_files, "Movie file not moved"
        assert "Inception.2010.1080p.srt" in inception_files, "Subtitle not moved"
        assert "Inception.2010.1080p.en.srt" in inception_files, "Subtitle not moved"
        
        # Check files inside Matrix folder
        matrix_files = os.listdir(matrix_dir)
        print(f"  Matrix folder contents: {matrix_files}")
        assert "The.Matrix.1999.mkv" in matrix_files, "Matrix movie file not moved"
        assert "The.Matrix.1999.srt" in matrix_files, "Matrix subtitle not moved"
        assert "The.Matrix.1999.nfo" in matrix_files, "Matrix info not moved"
        
        # Check history file
        history_file = os.path.join(temp_dir, ".organizer_history.json")
        assert os.path.exists(history_file), "History log was not written"
        print("Organization File Movement: PASSED")

        # 4. Test Undo / Restore
        print("\nRunning Undo last operation:")
        undo_res = temp_organizer.undo_last_action()
        assert undo_res is not None, "Undo returned None"
        success, failed = undo_res
        print(f"  Undo result: {success} restored, {failed} failed.")
        assert success == 8, f"Expected 8 files to be restored, got {success}"
        assert failed == 0, f"Expected 0 failures, got {failed}"
        
        # Verify files are back in original position
        for f in dummy_files:
            # except small_sample which wasn't moved
            if f != "small_sample.mp4":
                assert os.path.exists(os.path.join(temp_dir, f)), f"File {f} was not restored to root"
                
        # Verify folders are deleted (since they are now empty)
        assert not os.path.exists(inception_dir), "Inception folder was not cleaned up"
        assert not os.path.exists(matrix_dir), "Matrix folder was not cleaned up"
        
        # Verify history file is deleted or cleared
        assert not os.path.exists(history_file), "History file was not cleared"
        
        # 5. Test TV Show detection
        print("\nTesting TV Show Detection:")
        friends_ep1 = os.path.join(temp_dir, "Friends.S01E01.mp4")
        friends_ep2 = os.path.join(temp_dir, "Friends.S01E02.mp4")
        with open(friends_ep1, "w") as f:
            f.write("ep1")
        with open(friends_ep2, "w") as f:
            f.write("ep2")
            
        tv_movies, _ = temp_organizer.scan_movies(min_size_mb=0)
        friends_entries = [m for m in tv_movies if m['parsed_title'] == "Friends"]
        assert len(friends_entries) == 2, "Friends episodes not detected correctly"
        for m in friends_entries:
            assert m['is_tv_show'], "Friends episode not classified as TV show"
        print("  TV Show detection: PASSED")
        
        os.remove(friends_ep1)
        os.remove(friends_ep2)
        
        # 6. Test In-place subdirectory renaming
        print("\nTesting In-place Subdirectory Renaming:")
        sub_folder = os.path.join(temp_dir, "OldMovieFolder")
        os.makedirs(sub_folder, exist_ok=True)
        movie_in_sub = os.path.join(sub_folder, "Interstellar.2014.mp4")
        sub_in_sub = os.path.join(sub_folder, "Interstellar.2014.srt")
        with open(movie_in_sub, "w") as f:
            f.write("interstellar video")
        with open(sub_in_sub, "w") as f:
            f.write("interstellar sub")
            
        sub_movies, _ = temp_organizer.scan_movies(min_size_mb=0, scan_subfolders=True)
        interstellar_entry = next(m for m in sub_movies if m['parsed_title'] == "Interstellar")
        
        temp_organizer.organize_movies([interstellar_entry])
        
        new_folder = os.path.join(temp_dir, "Interstellar (2014)")
        assert os.path.exists(new_folder) and os.path.isdir(new_folder), "Subdirectory was not renamed"
        assert not os.path.exists(sub_folder), "Old subdirectory still exists"
        assert os.path.exists(os.path.join(new_folder, "Interstellar.2014.mp4")), "Movie file missing in renamed folder"
        assert os.path.exists(os.path.join(new_folder, "Interstellar.2014.srt")), "Subtitle file missing in renamed folder"
        print("  In-place subdirectory renaming: PASSED")
        
        # Test Undo of subdirectory renaming
        print("Testing Undo of Subdirectory Renaming:")
        undo_res_sub = temp_organizer.undo_last_action()
        assert undo_res_sub is not None, "Subdirectory undo returned None"
        success_sub, failed_sub = undo_res_sub
        assert success_sub == 3, f"Expected 3 files to be restored in subfolder undo, got {success_sub}"
        assert failed_sub == 0, f"Expected 0 failures in subfolder undo, got {failed_sub}"
        assert os.path.exists(sub_folder) and os.path.isdir(sub_folder), "Old subdirectory was not restored"
        assert not os.path.exists(new_folder), "New renamed folder still exists after undo"
        assert os.path.exists(movie_in_sub), "Movie file was not restored to original subfolder"
        assert os.path.exists(sub_in_sub), "Subtitle file was not restored to original subfolder"
        print("  Subdirectory renaming undo: PASSED")
        
        print("Undo / Restoration: PASSED")
        print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp directory: {temp_dir}")

if __name__ == "__main__":
    run_tests()
