"""The workflow's decisions as tested functions (Plan 5a P106, P117).

``ci`` reads artifacts and never builds them. The light modules (``context``, ``manifest``,
``summary``, ``switches``, ``verdict``, ``__main__``) import only the standard library,
``elections_calendar.model``, ``elections_calendar.text`` and each other, so the verdict job
runs without the virtual environment.
"""
