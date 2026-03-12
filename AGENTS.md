# Repository Guidelines

## Project Structure & Module Organization
- `manage.py`: Django entry point for local commands.
- `DjangoScoutingApp/`: project config (`settings.py`, `urls.py`, `asgi.py`, `wsgi.py`).
- `scouting/`: main app code (`models.py`, `views.py`, `forms.py`, `consumers.py`, `management/commands/`, `migrations/`).
- `scouting/templates/scouting/` and `templates/`: app and shared templates.
- `scouting/static/`: CSS, JS, fonts, and image assets.
- `media/images/`: uploaded media files.
- `scouting/tests.py`: current test module (expand here or split into a `scouting/tests/` package as coverage grows).

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\Scripts\activate` (Windows): create and activate virtual environment.
- `pip install -r requirements.txt`: install dependencies.
- `python manage.py migrate`: apply database migrations.
- `python manage.py runserver`: start local server at `http://127.0.0.1:8000/`.
- `python manage.py test`: run Django test suite.
- `python manage.py check`: run Django system checks.
- `python manage.py sync_teams_matches_tba` (and other `sync_*` commands): sync scouting/event data.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions/variables, `PascalCase` for classes and Django models.
- Keep views/forms thin where possible; move reusable logic into model methods or helper functions.
- Name migrations descriptively (auto-generated names are acceptable if accurate).

## Testing Guidelines
- Use Django `TestCase` for model/view/command behavior.
- Name tests `test_<behavior>` and keep one clear assertion purpose per test block.
- Add regression tests for bug fixes (especially for scoring, ranking, and sync logic).
- Run `python manage.py test` before opening a PR.

## Commit & Pull Request Guidelines
- Match existing history: short, imperative commit subjects (examples: `Fix priority column`, `Add comment field`).
- Keep commits focused; separate refactors from behavior changes.
- Reference issues in commit/PR text when applicable (for example, `Closes #38`).
- PRs should include: summary, affected areas, migration notes, manual test steps, and screenshots for UI changes.

## Security & Configuration Tips
- Do not commit real secrets, API keys, or production credentials.
- Prefer environment variables/local overrides for sensitive settings (for example TBA or sync credentials).
- Validate `ALLOWED_HOSTS`, `DEBUG`, and sync endpoints before deployment.
