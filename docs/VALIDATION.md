\# Validation Workflow



Before any merge, run:



```bash

python3 -m py\_compile \\

&#x20; 04\_filter\_quality.py \\

&#x20; 05\_run\_pipeline.py \\

&#x20; 13\_city\_guard.py \\

&#x20; 14\_evidence\_gate.py \\

&#x20; 15\_run\_pipeline\_guarded.py



python3 15\_run\_pipeline\_guarded.py



python3 -m pytest -q

