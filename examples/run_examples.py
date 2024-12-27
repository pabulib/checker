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

    results = checker.process_files([valid_file_path])

    # print(json.dumps(results["summary"], indent=4))

    # print(json.dumps(results["metadata"], indent=4))
    print(json.dumps(results, indent=4))

    # checker.process_files([valid_file_path, invalid_file_path])

    # with open(valid_file_path, "r") as valid_file:
    #     valid_content = valid_file.read()
    # with open(invalid_file_path, "r") as invalid_file:
    #     invalid_content = invalid_file.read()

    # checker.process_files([valid_content, invalid_content])


if __name__ == "__main__":
    main()
