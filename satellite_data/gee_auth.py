# gee_auth.py
import ee

def setup_gee():
    """
    Authenticates and Initializes Google Earth Engine.
    """
    
    project_id = 'agro-speaking' 
    
    try:
        ee.Initialize(project=project_id)
        print("✅ GEE Initialization Successful: You already authenticated!")
        return True
    
    except Exception as e:
        print("⚠️ Authentication required. Browser will pop up, please allow access...")
        try:
            ee.Authenticate()
            ee.Initialize(project=project_id)
            print("✅ GEE Authentication and Initialization Successful!")
            return True
            
        except Exception as auth_error:
            print(f"❌ Setup Failed: {auth_error}")
            return False

if __name__ == "__main__":
    print("Starting gee_auth.py debugging block...")
    success = setup_gee()
    
    if success:
        print("\n--- Authentication Successful ---")
        print("You can now safely import and use 'setup_gee' in main.py")