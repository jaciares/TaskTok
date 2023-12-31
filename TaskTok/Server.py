
#import logging

from flask import Flask, jsonify, request, render_template, make_response

from .extensions import db, jwtManager
from .models import User, NoNoTokens
from .schema import UserSchema
from RemindMeClient.celeryManager import celery_init_app
from celery import Celery
from RemindMeClient import task
import inspect
#keycloak_client = Client('192.168.1.26/kc/callback')
def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///db.sqlite3"
    app.config['SQLALCHEMY_ECHO'] = True
    app.config['SECRET_KEY'] = r'HJDNUIWQEYH156345357564@@!@$'
    app.config['JWT_SECRET_KEY'] = r'CHANGEMELATER-JWTSECRET'
    app.config['JWT_TOKEN_LOCATION'] = ['cookies']
    
    #app.config['CELERY_BROKER_URL'] = 'pyamqp://admin:password@localhost/tasktok'
    #app.config['CELERY_RESULT_BACKEND'] = 'rpc://'
    app.config.from_mapping(
    CELERY=dict(
        broker_url='pyamqp://admin:password@localhost:5672/tasktok',
        #result_backend='rpc://admin:password@localhost:5672/tasktok',
        task_ignore_result=True,
    ),
)


    
    db.init_app(app)  # Initialize the db extension with app
    jwtManager.init_app(app)
    celery_app = celery_init_app(app)


    # Register blueprints:
    from .blueprints import api as api_blueprint
    from .blueprints import auth as auth_blueprint
    from .blueprints import views as views_blueprint
    app.register_blueprint(api_blueprint.api, url_prefix='/api')
    app.register_blueprint(auth_blueprint.auth, url_prefix='/auth')
    app.register_blueprint(views_blueprint.views, url_prefix='/')

    @app.errorhandler(404)
    def pageNotFound(error):
        return render_template("error/notFound.html"),404

    @jwtManager.user_identity_loader
    def UserIdentityLookup(user):
        return user.id
    
    @jwtManager.user_lookup_loader
    def searchLoggedInUser(_jwt_header, jwt_data):
        identity = jwt_data['sub']
        print(identity)
           
        return User.query.get(identity)
        
    #additional claims for roles 'admin'?
    @jwtManager.additional_claims_loader
    def addAdditionalClaims(identity):
        
        if identity.username == "admin":
            return {"is_admin" : True}
        else:
            return {"is_admin" : False}

    @jwtManager.expired_token_loader
    def expiredTokenCallback(jwt_header, jwt_data):
        acceptHeader = request.headers.get('Accept','')
        response = make_response()
        if 'application/json' in acceptHeader:
            response.data = jsonify({"Message": "Token has expired", "Error": "token_expired"})
            response.status_code = 401
            response.content_type = 'application/json'
            
        else:
            response.data = render_template("error/sessionExpired.html")
            response.status_code = 401
            response.content_type = 'text/html'
        #set the access token to null, otherwise if they keep going to protected pages, they'll get session expired.
        #this will set up future requests to say not authenticated (or redirect to login)
        response.set_cookie("access_token_cookie", "", max_age=0)
        return response
    
    @jwtManager.invalid_token_loader
    def expiredTokenCallback(error):
        return jsonify({"Message": "Signature validation failed", "Error": "token_invalid"}),401
    
    @jwtManager.unauthorized_loader
    def unauthorizedTokenCallback(error):
        acceptHeader = request.headers.get('Accept','')
        response = make_response()
        if 'application/json' in acceptHeader:
            response.data = jsonify({"Message": "API call missing a token", "Error": "token_missing"})
            response.status_code = 401
            response.content_type = 'application/json'
            
        else:
            response.data = render_template("error/notLoggedIn.html")
            response.status_code = 401
            response.content_type = 'text/html'       
        return response


    @jwtManager.token_in_blocklist_loader
    def tokenIsRevokedCallback(jwt_header, jwt_data):
        jti = jwt_data['jti']

        token = db.session.query(NoNoTokens).filter(NoNoTokens.jti == jti).scalar()

        if token is not None:
            return True
        else: 
            return False
        
    @jwtManager.revoked_token_loader
    def tokenWasRevoked(jwt_header, jwt_data):
        return jsonify({"Message": "The supplied token was revoked already", "Error": "token_revoked"}),401


    


    return app