import json
import os

from pabulib.checker import Checker


def main():
    # Create paths to example files
    base_dir = os.path.abspath("examples")
    valid_file_path = os.path.join(base_dir, "example_valid.pb")
    invalid_file_path = os.path.join(base_dir, "example_invalid.pb")

    # Initialize the checker
    checker = Checker()

    # Process the valid file
    results = checker.process_files([valid_file_path])
    print("Results for valid file:")
    print(json.dumps(results, ensure_ascii=False, indent=4))

    # Process the invalid file
    results = checker.process_files([invalid_file_path])
    print("Results for invalid file:")
    print(json.dumps(results, ensure_ascii=False, indent=4))

    # from contents
    # with open(valid_file_path, "r") as valid_file:
    #     valid_content = valid_file.read()
    # with open(invalid_file_path, "r") as invalid_file:
    #     invalid_content = invalid_file.read()

    # checker.process_files([valid_content, invalid_content])


if __name__ == "__main__":
    main()
