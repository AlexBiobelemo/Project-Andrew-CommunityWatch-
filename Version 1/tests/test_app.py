def test_index_page(client):
    """
    GIVEN a Flask application
    WHEN the '/' page is requested (GET)
    THEN check that the response is valid
    """
    response = client.get('/')
    assert response.status_code == 200
    assert b"CommunityWatch" in response.data

def test_protected_page_redirects(client):
    """
    GIVEN a Flask application
    WHEN a protected page (like /issue/1) is requested by an anonymous user
    THEN check that the user is redirected to the login page
    """
    response = client.get('/issue/1')
    # 302 is the status code for a redirect
    assert response.status_code == 302
    # Check if the string 'login' is in the redirect URL string
    assert 'login' in response.headers['Location']

