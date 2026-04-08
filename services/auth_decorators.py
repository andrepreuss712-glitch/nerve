from functools import wraps
from flask import g, abort


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not getattr(g, 'user', None) or not getattr(g.user, 'is_superadmin', False):
            abort(403)
        return f(*args, **kwargs)
    return wrapper
