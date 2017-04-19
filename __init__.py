from flask import Flask, render_template, url_for, request, redirect, flash, jsonify
from database_setup import Base, Restaurant, MenuItem, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from functools import wraps 

engine = create_engine("postgresql://catalog:catalog@localhost/catalog")
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine, autocommit=True)
session = DBSession()

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('/var/www/catalog/catalog/client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect ('/login')
        return f(*args, **kwargs)
    return decorated_function

# gconnect and gdisconnect functions obtained from the instructor notes


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('/var/www/catalog/catalog/client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1].decode("utf8"))
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: '
    '150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# Adding new user to database


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.begin()
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except Exception:
        return None


@app.route("/gdisconnect")
def gdisconnect():
    # Only disconnect a connect user
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Execute HTTP GET request to revoke current token.
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % credentials
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        # Reset the user's session.
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response

# JSONified routes


@app.route('/restaurants/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def restaurantItemJSON(restaurant_id, menu_id):
    menuitem = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(MenuItem=menuitem.serialize)


@app.route('/restaurants/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant.id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurants/JSON')
def restaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(
        Restaurants=[restaurant.serialize for restaurant in restaurants])

# functions for authentication


@app.route('/login')
def showLogin():
    state = ''.join(
        random.choice(
            string.ascii_uppercase +
            string.digits)for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# routing functions for restaurants
@app.route('/')
@app.route('/restaurants')
def showRestaurants():
    restaurants = session.query(Restaurant).all()
    if 'username' not in login_session:
        return render_template('publicrestaurants.html', restaurants=restaurants)
    else:
        return render_template('restaurants.html', restaurants=restaurants)


@app.route('/restaurant/new', methods=['GET', 'POST'])
@login_required
def newRestaurant():
    if request.method == 'POST':
        newrestaurant = Restaurant(
            name=request.form['name'],
            user_id=login_session['user_id'])
        session.begin()
        session.add(newrestaurant)
        session.commit()
        flash('New restaurant created!')
        return redirect(url_for('showRestaurants'))
    else:
        return render_template('newRestaurant.html')


@app.route('/restaurant/<int:restaurant_id>/edit', methods=['GET', 'POST'])
@login_required
def editRestaurant(restaurant_id):
        editedrestaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
        if editedrestaurant.user_id != login_session['user_id']:
            flash('You cannot edit %s'%editedrestaurant.name)
            return redirect(url_for('showRestaurants'))
        if request.method == 'POST':
            if request.form['name']:
                editedrestaurant.name = request.form['name']
                session.begin()
                session.add(editedrestaurant)
                session.commit
                flash('Restaurant sucessfully edited')
                return redirect(url_for('showRestaurants'))
        else:
            restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
            return render_template(
                'editRestaurant.html',
                restaurant_id=restaurant_id,
                restaurant=restaurant)


@app.route('/restaurant/<int:restaurant_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteRestaurant(restaurant_id):
    deleterestaurant = session.query(
        Restaurant).filter_by(id=restaurant_id).one()
    if deleterestaurant.user_id != login_session['user_id']:
        flash('You cannot delete %s'%deleterestaurant.name)
        return redirect(url_for('showRestaurants'))

    if request.method == 'POST':
        session.begin()
        session.delete(deleterestaurant)
        session.commit()
        flash('Restaurant sucessfully deleted')
        return redirect(url_for('showRestaurants'))

    else:
        restaurant = session.query(
            Restaurant).filter_by(id=restaurant_id).one()
        return render_template(
            'deleteRestaurant.html',
            restaurant_id=restaurant_id,
            restaurant=restaurant)

# routing functions for menu items


@app.route('/restaurant/<int:restaurant_id>/menu')
@app.route('/restaurant/<int:restaurant_id>')
def showMenu(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant_id).all()
    creator = getUserID(restaurant.user_id)
    if 'username' not in login_session or restaurant.user_id != login_session['user_id']:
        return render_template(
            'publicmenu.html',
            items=items,
            restaurant=restaurant,
            creator=creator)
    else:
        return render_template('menu.html', restaurant=restaurant, items=items)


@app.route('/restaurant/<int:restaurant_id>/menu/new', methods=['GET', 'POST'])
@login_required
def newMenuItem(restaurant_id):
    if request.method == 'POST':
        newmenuitem = MenuItem(
            name=request.form['name'],
            price=request.form['price'],
            description=request.form['description'],
            course=request.form['course'],
            user_id=login_session['user_id'],
            restaurant_id=restaurant_id)
        session.begin()
        session.add(newmenuitem)
        session.commit()
        flash("new menu item created!")
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))

    else:
        return render_template('newMenuItem.html', restaurant_id=restaurant_id)


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit',
           methods=['GET', 'POST'])
@login_required
def editMenuItem(restaurant_id, menu_id):
    editmenuitem = session.query(MenuItem).filter_by(id=menu_id).one()

    if editmenuitem.user_id != login_session['user_id']:
        flash('You cannot edit %s'%editmenuitem.name)
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))

    if request.method == 'POST':
        editmenuitem.name = request.form['name']
        editmenuitem.price = request.form['price']
        editmenuitem.description = request.form['description']
        editmenuitem.course = request.form['course']
        session.begin()
        session.add(editmenuitem)
        session.commit()
        flash("Menu item was edited")
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))

    else:
        item = session.query(MenuItem).filter_by(id=menu_id).one()
        return render_template('editMenuItem.html',
                               item=item, restaurant_id=restaurant_id)


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteMenuItem(restaurant_id, menu_id):
    item = session.query(MenuItem).filter_by(id=menu_id).one()

    if item.user_id != login_session['user_id']:
        flash('You cannot delete %s'%item.name)
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))


    if request.method == 'POST':
        session.begin()
        session.delete(item)
        session.commit()
        flash("Menu item was deleted")
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))

    else:
        item = session.query(MenuItem).filter_by(id=menu_id).one()
        return render_template('deleteMenuItem.html',
                               item=item, restaurant_id=restaurant_id)


if (__name__) == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run()
# comment