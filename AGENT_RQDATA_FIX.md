# RQData Connection Fix Note

This note is for the agent responsible for `/Users/yupeishen/Desktop/quant_platform`.

## What was broken

RQData did not connect because the initialization code used login forms that are not valid for the current license key and installed `rqdatac` version.

The old code tried:

```python
rqdatac.init(license=settings.rqdata_license)
```

On the tested `rqdatac` versions this fails with:

```text
ValueError: username/password/addr or uri expected
```

The fallback URI form was also tested:

```python
rqdatac.init(uri="rqdata://license:...@rqdatad-pro.ricequant.com:16011")
```

For this key, that fails with an authentication error.

## What was changed

`src/rq_platform/data_sources/rqdata_source.py` now uses the verified license-key login form:

```python
rqdatac.init(username="license", password=settings.rqdata_license)
```

The license is still read from project root `.env` through `settings.rqdata_license`. Do not print or commit the license key.

## Correct environment

This project should use the conda environment named `quant_platform`:

```bash
conda activate quant_platform
```

The environment path observed on this machine is:

```text
/opt/miniconda3/envs/quant_platform
```

It uses Python 3.11.15, which matches the project requirement:

```toml
requires-python = ">=3.11"
```

Ignore the local `.venv` unless the project owner explicitly decides to remove or rebuild it. The real runtime should be conda.

## Verification command

Use this exact check from project root:

```bash
cd /Users/yupeishen/Desktop/quant_platform
conda activate quant_platform
PYTHONPATH=src python scripts/01_check_rqdata.py
```

Expected result:

```text
license exists: yes
initialized: True
quota returned successfully
```

## Additional compatibility note

`settings.py` was changed from:

```python
rqdata_license: str | None = None
```

to:

```python
from typing import Optional
rqdata_license: Optional[str] = None
```

This is harmless on Python 3.11 and also keeps the file importable if someone accidentally uses Python 3.9. The main fix remains the RQData login form above.
