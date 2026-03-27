from app import app, init_db

# Initialize database on startup (required for Render)
init_db()

if __name__ == "__main__":
    app.run()
