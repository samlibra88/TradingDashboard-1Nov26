# access_token_generator.py - Generate Zerodha access token

from kiteconnect import KiteConnect
import config

def generate_access_token():
    """
    Generate access token for Zerodha API
    
    Steps:
    1. Run this script
    2. Visit the URL provided
    3. Login with your Zerodha credentials
    4. You'll be redirected - copy the REQUEST_TOKEN from URL
    5. Paste the REQUEST_TOKEN when prompted
    6. The script will generate your ACCESS_TOKEN
    7. Update config.py with the new ACCESS_TOKEN
    """
    
    print("=" * 60)
    print("ZERODHA ACCESS TOKEN GENERATOR")
    print("=" * 60)
    
    kite = KiteConnect(api_key=config.API_KEY)
    
    # Get login URL
    login_url = kite.login_url()
    print(f"\n1. Open this URL in your browser:\n{login_url}\n")
    print("2. Login with your Zerodha credentials")
    print("3. You will be redirected - copy the REQUEST_TOKEN from the URL")
    print("   (It will be in the format: request_token=xxxxx)\n")
    
    # Get request token from user
    request_token = input("Enter your REQUEST_TOKEN: ").strip()
    
    try:
        # Generate session
        data = kite.generate_session(
            request_token=request_token,
            api_secret=config.API_SECRET
        )
        
        access_token = data["access_token"]
        
        print("\n" + "=" * 60)
        print("✓ ACCESS TOKEN GENERATED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\nYour ACCESS_TOKEN:\n{access_token}\n")
        print("Update config.py with this token:")
        print(f"ACCESS_TOKEN = \"{access_token}\"\n")
        print("=" * 60)
        
        return access_token
    
    except Exception as e:
        print(f"\n✗ Error generating token: {e}")
        print("\nCommon issues:")
        print("- Request token is invalid or expired")
        print("- API key or secret is incorrect")
        print("- Check your config.py settings\n")
        return None


if __name__ == "__main__":
    generate_access_token()
