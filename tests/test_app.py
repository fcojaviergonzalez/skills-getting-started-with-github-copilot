"""
Tests for the Mergington High School Activities Application
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities before each test"""
    # Save original state
    original_activities = {}
    from app import activities
    for key, value in activities.items():
        original_activities[key] = {
            "description": value["description"],
            "schedule": value["schedule"],
            "max_participants": value["max_participants"],
            "participants": value["participants"].copy()
        }
    
    yield
    
    # Restore original state
    for key in activities:
        activities[key]["participants"] = original_activities[key]["participants"].copy()


class TestGetActivities:
    """Tests for the GET /activities endpoint"""
    
    def test_get_activities(self, client):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        # Check that we have activities
        assert isinstance(data, dict)
        assert len(data) > 0
        
        # Check that required fields exist in each activity
        for activity_name, activity in data.items():
            assert "description" in activity
            assert "schedule" in activity
            assert "max_participants" in activity
            assert "participants" in activity
            assert isinstance(activity["participants"], list)
    
    def test_chess_club_exists(self, client):
        """Test that Chess Club activity exists"""
        response = client.get("/activities")
        data = response.json()
        
        assert "Chess Club" in data
        assert data["Chess Club"]["max_participants"] == 12


class TestSignup:
    """Tests for the POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_new_participant(self, client, reset_activities):
        """Test signing up a new participant"""
        from app import activities
        
        initial_count = len(activities["Chess Club"]["participants"])
        
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Signed up newstudent@mergington.edu for Chess Club"
        
        # Verify participant was added
        assert len(activities["Chess Club"]["participants"]) == initial_count + 1
        assert "newstudent@mergington.edu" in activities["Chess Club"]["participants"]
    
    def test_signup_duplicate_participant(self, client, reset_activities):
        """Test signing up a participant who is already registered"""
        response = client.post(
            "/activities/Chess Club/signup?email=michael@mergington.edu"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_nonexistent_activity(self, client):
        """Test signing up for an activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Club/signup?email=student@mergington.edu"
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_signup_multiple_activities(self, client, reset_activities):
        """Test signing up the same student to multiple activities"""
        from app import activities
        
        email = "multisport@mergington.edu"
        
        # Sign up for Basketball
        response1 = client.post(
            f"/activities/Basketball/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Sign up for Tennis Club
        response2 = client.post(
            f"/activities/Tennis Club/signup?email={email}"
        )
        assert response2.status_code == 200
        
        # Verify student is in both activities
        assert email in activities["Basketball"]["participants"]
        assert email in activities["Tennis Club"]["participants"]


class TestUnregister:
    """Tests for the POST /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant(self, client, reset_activities):
        """Test unregistering an existing participant"""
        from app import activities
        
        # michael@mergington.edu is in Chess Club
        initial_count = len(activities["Chess Club"]["participants"])
        
        response = client.post(
            "/activities/Chess Club/unregister?email=michael@mergington.edu"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Unregistered michael@mergington.edu from Chess Club"
        
        # Verify participant was removed
        assert len(activities["Chess Club"]["participants"]) == initial_count - 1
        assert "michael@mergington.edu" not in activities["Chess Club"]["participants"]
    
    def test_unregister_nonexistent_participant(self, client):
        """Test unregistering a participant who is not registered"""
        response = client.post(
            "/activities/Chess Club/unregister?email=notregistered@mergington.edu"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "not signed up" in data["detail"]
    
    def test_unregister_nonexistent_activity(self, client):
        """Test unregistering from an activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Club/unregister?email=student@mergington.edu"
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_signup_and_unregister(self, client, reset_activities):
        """Test signing up and then unregistering"""
        from app import activities
        
        email = "testuser@mergington.edu"
        activity = "Programming Class"
        
        # Sign up
        response1 = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert response1.status_code == 200
        assert email in activities[activity]["participants"]
        
        # Unregister
        response2 = client.post(
            f"/activities/{activity}/unregister?email={email}"
        )
        assert response2.status_code == 200
        assert email not in activities[activity]["participants"]


class TestActivityCapacity:
    """Tests for managing capacity limits"""
    
    def test_participant_count_accuracy(self, client, reset_activities):
        """Test that participant counts are accurate"""
        from app import activities
        
        response = client.get("/activities")
        data = response.json()
        
        # Verify that stated max_participants is sensible
        for activity_name, activity in data.items():
            assert activity["max_participants"] > 0
            assert len(activity["participants"]) <= activity["max_participants"]
            
            # Calculate spots left (implicit in the UI)
            spots_left = activity["max_participants"] - len(activity["participants"])
            assert spots_left >= 0
