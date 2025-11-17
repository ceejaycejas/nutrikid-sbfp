from app import create_app

# Expose a WSGI-compatible app object for production servers (e.g., gunicorn, waitress)
app = create_app()

# Enhanced developer-friendly startup (merged from previous start.py)
import os
import sys
import socket
import webbrowser
from threading import Timer


def check_port(port):
    """Check if a port is available"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result != 0


def find_available_port(start_port=8000, max_port=8100):
    """Find an available port starting from start_port"""
    for port in range(start_port, max_port):
        if check_port(port):
            return port
    return None


def open_browser(url):
    """Open browser after a delay"""
    def open_url():
        try:
            webbrowser.open(url)
            print(f"🌐 Opening browser at {url}")
        except Exception as e:
            print(f"Could not open browser automatically: {e}")
            print(f"Please manually open: {url}")

    Timer(2.0, open_url).start()


def setup_environment():
    """Set up the environment for the application"""
    # Add current directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    # Set environment variables if not already set
    if not os.getenv('FLASK_APP'):
        os.environ['FLASK_APP'] = 'app.py'

    if not os.getenv('FLASK_ENV'):
        os.environ['FLASK_ENV'] = 'development'


def print_startup_info(port):
    """Print startup information"""
    print("🚀 Starting NutriKid Application")
    print("=" * 50)
    print(f"📍 Local URL: http://localhost:{port}")
    print(f"📍 Network URL: http://127.0.0.1:{port}")
    print("=" * 50)
    print("📋 Available Features:")
    print("  ✅ User Management")
    print("  ✅ School Administration")
    print("  ✅ Student Registration")
    print("  ✅ BMI Monitoring")
    print("")
    print("  ✅ Dashboard Analytics")
    print("  ✅ Reports & Export")
    print("=" * 50)
    print("🔑 Default Login Credentials:")
    print("  Super Admin: superadmin / admin123")
    print("  School Admin: admin / admin123")
    print("=" * 50)
    print("⚠️  Press Ctrl+C to stop the server")
    print("=" * 50)


def main():
    """Main startup function for developer runs"""
    try:
        # Setup environment
        setup_environment()

        # Use the global app created above
        # Removed global app declaration since it's not needed

        # Find available port
        port = find_available_port()
        if not port:
            print("❌ No available ports found in range 8000-8100")
            print("Please close other applications using these ports and try again.")
            return False

        # Print startup information
        print_startup_info(port)

        # Open browser automatically
        open_browser(f"http://localhost:{port}")

        # Start the application
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            use_reloader=False  # Disable reloader to prevent double startup
        )

        return True

    except ImportError as e:
        print("❌ Import Error:")
        print(f"   {e}")
        print("\n💡 Solutions:")
        print("   1. Run the deployment script first: python deploy.py")
        print("   2. Install dependencies: pip install -r requirements.txt")
        print("   3. Activate virtual environment if using one")
        return False

    except Exception as e:
        print(f"❌ Startup Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check if MySQL is running")
        print("   2. Verify database configuration in .env file")
        print("   3. Run deployment script: python deploy.py")
        return False


if __name__ == '__main__':
    try:
        success = main()
        if not success:
            input("\nPress Enter to exit...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 NutriKid application stopped by user")
        print("Thank you for using NutriKid!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)