Install locally as python package:

```
pip install git+https://github.com/pabulib/checker.git
```

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
checker.process_files([pb_file_path])
```

2. directly from provided content
```
# FROM CONTENTS

with open(pb_file_path, "r") as valid_file:
    valid_content = valid_file.read()

checker.process_files([valid_content])
```