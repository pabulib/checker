import os

from pabulib.checker import Checker


def create_example_paths(directory: str):
    """
    Create absolute paths for example files in the given directory.

    Args:
        directory (str): The directory containing the example files.

    Returns:
        dict: A dictionary with paths to the example files.
    """
    base_dir = os.path.abspath(directory)
    valid_file_path = os.path.join(base_dir, "example_valid.pb")
    invalid_file_path = os.path.join(base_dir, "example_invalid.pb")
    invalid_file_path_2 = os.path.join(base_dir, "example_invalid_2.pb")
    return invalid_file_path_2, invalid_file_path


def main():
    # Create paths to example files
    invalid_file_path_2, invalid_file_path = create_example_paths("examples")

    # Initialize the checker
    checker = Checker()

    checker.process_files([invalid_file_path, invalid_file_path_2])

    # checker.process_files([valid_file_path, invalid_file_path])

    # with open(valid_file_path, "r") as valid_file:
    #     valid_content = valid_file.read()
    # with open(invalid_file_path, "r") as invalid_file:
    #     invalid_content = invalid_file.read()

    # checker.process_files([valid_content, invalid_content])


if __name__ == "__main__":
    main()
