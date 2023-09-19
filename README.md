## PDF WAM
This is a rewrite of Egovmon/Tingtun PDF WAM rewrite. This rewrite focuses on,

1. Update to the latest `PyPDF2` library.
2. Drop dependencies on deprecated libraries.
3. Merge and remove ununsed modules.
4. Use consistent naming of functions, such as replacing `camelCase` functions with `snake_case`
5. Make the code run as a HTTP server backend similar to current PDF WAM.

## Setup

Make sure you have `python3` with virtual environment support. This can be done by installing,

	sudo apt install python3-venv -y

Create a virtual environment, say `pdfwam` and switch to it

	python3 -m venv pdfwam; source pdfwam/bin/activate

Install the requirements.

	pip install -r requirements.txt
