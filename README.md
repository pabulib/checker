Install locally as python package:

```
pip install git+https://github.com/pabulib/checker.git
```

### TODO
1. pycountry should be installed

import as

```
from pabulib.checker import Checker
```

example of usage:

You can use `process_files` method which takes a list of path to files or their contents.

```
from pabulib.checker import Checker

pb_file_path = (
    "<example>/pabulib_checker/examples/example_valid.pb"
)

# Initialize the checker
checker = Checker()
```

1. from path

```
# FROM FILES
results = checker.process_files([pb_file_path])
```

2. directly from provided content
```
# FROM CONTENTS

with open(pb_file_path, "r") as valid_file:
    valid_content = valid_file.read()

results = checker.process_files([valid_content])
```

Get the results. Results is a python dict (JSON)
```
print(results["summary"]) # for a summary, errors accross all files
print(results["metadata"]) # processing metadata, how many files were processed etc

print(results) # to get details.
# for example
print(results[<file_name>])
```