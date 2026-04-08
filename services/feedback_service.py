import os
import uuid
from werkzeug.utils import secure_filename
from database.models import Feedback

UPLOAD_DIR = os.environ.get('FEEDBACK_UPLOAD_DIR', '/opt/nerve/uploads/feedback')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_MIME = {'image/png', 'image/jpeg', 'image/webp'}


def _ensure_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_screenshot(file_storage):
    """Speichert einen Screenshot auf Disk. Gibt relativen Pfad zurück oder None."""
    if not file_storage or not file_storage.filename:
        return None
    if (file_storage.mimetype or '') not in ALLOWED_MIME:
        raise ValueError('invalid mime')
    ext = file_storage.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError('invalid ext')
    _ensure_dir()
    name = f"{uuid.uuid4().hex}.{ext}"
    abs_path = os.path.join(UPLOAD_DIR, secure_filename(name))
    file_storage.save(abs_path)
    return f"feedback/{name}"  # relativ


def create_feedback(db, user_id, org_id, typ, text, screenshot_rel=None,
                    context_url=None, rating=None, kategorie=None):
    """Erstellt einen Feedback-Datensatz und committet ihn."""
    fb = Feedback(
        user_id=user_id,
        org_id=org_id,
        typ=typ,
        text=text,
        screenshot_path=screenshot_rel,
        context_url=context_url,
        rating=rating,
        kategorie=kategorie,
    )
    db.add(fb)
    db.commit()
    return fb
