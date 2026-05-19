import os
from flask import Flask

from app.config import BASE_DIR


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = os.urandom(24)

    @app.context_processor
    def inject_translations():
        from app.i18n import get_translations
        return {"t": get_translations()}

    from app.web.routes import bp
    app.register_blueprint(bp)

    return app
