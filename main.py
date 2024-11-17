# PROFESSIONAL PROJECT: E-Commerce Website

# OBJECTIVE: To implement an e-commerce website which can:
#            1. Display items for sale and take payment from users.
#            2. Include a working cart and checkout.
#            3. Have login/registration authentication features.

# Import necessary libraries:
from data import app, db, API_STRIPE_KEY_TEST_SECRET, RATE_SALES_TAX, RATE_SHIPPING, SECRET_KEY_FOR_CSRF_PROTECTION, SENDER_EMAIL_GMAIL, SENDER_HOST, SENDER_PASSWORD_GMAIL, SENDER_PORT, SITE_DOMAIN
from data import CartDetails, Orders, OrderDetails, ProductCategories, Products, UnitsOfMeasure, Users
from data import AddProductToCartForm, AddOrEditProductForm, AddOrEditProductCategoryForm, AddOrEditUOMForm, AddOrEditUserForm, ContactForm, EditCartDetailForm, EditOrderForm, LoginForm, RegisterForm
from datetime import datetime
import email_validator
from flask import abort, Flask, flash, redirect, render_template, request, url_for
from flask_bootstrap import Bootstrap5
from flask_login import current_user, login_required, login_user, LoginManager, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from functools import wraps  # Used in 'admin_only" decorator function
import os
from sqlalchemy import and_, Boolean, DateTime, Float, ForeignKey, func, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import smtplib
import stripe
import traceback
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import BooleanField, DateField, DecimalField, EmailField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField, validators
from wtforms.validators import Email, InputRequired, Length, NumberRange, Optional
import wx

# Define variable to be used for showing user dialog and message boxes:
dlg = wx.App()

# # Set Stripe secret API key:
# stripe.api_key = API_STRIPE_KEY_TEST_SECRET

# Initialize the Flask app. object:
app = Flask(__name__)

# Initialize variable to track whether a logged-in user is an admin
admin = False

# Create needed class "Base":
class Base(DeclarativeBase):
    pass

# NOTE: Additional configurations are launched via the "run_app" function defined below.


# CONFIGURE ROUTES SPECIFIC TO USER AUTHENTICATION AND ADMIN-SPECIFIC RESTRICTIONS:
# ***********************************************************************************************************
# Configure the Flask login manager:
login_manager = LoginManager()
login_manager.init_app(app)


# Implement a user loader callback (to facilitate loading current user into session):
@login_manager.user_loader
def load_user(user_id):
    return retrieve_from_database("get_user_by_id", user_id=user_id)


# Implement a decorator function to ensure that only someone who knows the admin password can access
# "admin-level" functionality of the website:
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If not the admin then return abort with 403 error:
        if not (current_user.is_authenticated and current_user.id == 1):
            return abort(403)

        # At this point, user is the admin, so proceed with allowing access to the route:
        return f(*args, **kwargs)

    return decorated_function


# CONFIGURE ROUTES FOR WEB PAGES (LISTED IN HIERARCHICAL ORDER STARTING WITH HOME PAGE, THEN ALPHABETICALLY):
# ***********************************************************************************************************
# Configure route for home page:
@app.route('/',methods=["GET", "POST"])
def home():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Build list of tabs so as to display products by each active product category:
        product_tab_dict = {}
        i = 1
        for item in active_product_categories:
            product_tab_dict[item.name] = f"tab-{i}"
            i += 1

        # Build a dictionary containing active products (along with counts) for active product categories:
        active_prod_dict = {}
        for item in active_product_categories:
            active_products, active_prod_count = get_active_products_by_category(item.category_id)
            active_prod_dict[item.name] = {"count": active_prod_count, "records": active_products}

        # Go to the home page:
        return render_template("index.html", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, product_tab_dict=product_tab_dict, active_prod_dict=active_prod_dict, admin=admin)

    except:
        # Log error into system log file:
        update_system_log("route: '/'", traceback.format_exc())

        # Go to the home page and display error details to the user:
        return render_template("index.html", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, product_tab_dict=product_tab_dict, active_prod_dict=active_prod_dict, admin=admin)


# Configure route for "About" web page:
@app.route('/about')
def about():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Go to the "About" page:
        return render_template("about.html", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:
        # Log error into system log:
        update_system_log("route: '/about'", traceback.format_exc())

        # Go to the "About" page and display error details to the user:
        return render_template("about.html", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Add Product Category" web page:
@app.route('/add_prod_cat',methods=["GET", "POST"])
@admin_only
def add_prod_cat():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Instantiate an instance of the "AddOrEditUOMForm" class:
        form = AddOrEditProductCategoryForm()

        # Validate form entries upon submittal. If validated, send message:
        if form.validate_on_submit():
            # Initialize variables to be used in processing add request:
            msg_status = ""
            error_msg = ""

            # Check if product category already exists in the db.  Capture feedback to relay to end user:
            prod_cat_in_db = retrieve_from_database("get_prod_cat_by_name", prod_cat_name=form.txt_name.data)
            if prod_cat_in_db == {}:
                error_msg = "An error has occurred. Product category has not been added."
            elif prod_cat_in_db != None:
                msg_status = f"Product category '{form.txt_name.data}' already exists in the database.  Please go back and enter a unique product category."
            else:
                # Add the new product category record to the database.  Capture feedback to relay to end user:
                if not update_database("add_prod_cat", form=form):
                    error_msg = "An error has occurred. Product category has not been added."
                else:
                    msg_status = "Product category has been successfully added."

            # Go to the product-category administration page and display the results of database update:
            return render_template("admin_prod_cat.html", trans_type="Add", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Go to the product-category administration page:
        return render_template("admin_prod_cat.html", trans_type="Add", form=form, msg_status=None, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/add_prod_cat'", traceback.format_exc())

        # Go to the product-category administration page and display error details to the user:
        return render_template("admin_prod_cat.html", trans_type="Add", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Add Product" web page:
@app.route('/add_product',methods=["GET", "POST"])
@admin_only
def add_product():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Instantiate an instance of the "AddOrEditProductForm" class:
        form = AddOrEditProductForm()

        # Initialize variables to be used in capturing anomalies encountered during population of selection lists on the form:
        msg_status = None
        error_msg = ""

        # Populate the product category selection list on the form:
        prod_cats_for_selection = []
        prod_cats, prod_cat_count = get_product_categories_for_selection()
        if prod_cats == {}:
            error_msg = "An error has occurred in populating the Product Category selection list."
        elif prod_cat_count == 0:
            msg_status = "No selections are available for Product Category."
        else:
            for prod_cat in prod_cats:
                prod_cats_for_selection.append((prod_cat.category_id, f"{prod_cat.name} ({prod_cat.description})"))
            form.lst_prod_cat.choices = prod_cats_for_selection

        # Populate the units of measure selection list on the form:
        uoms_for_selection = []
        uoms, uom_count = get_uoms_for_selection()
        if uoms == {}:
            error_msg = "An error has occurred in populating the Unit of Measure (UOM) selection list."
        elif uom_count == 0:
            msg_status = "No selections are available for Unit of Measure (UOM)."
        else:
            for uom in uoms:
                uoms_for_selection.append((uom.uom_id, f"{uom.code} ({uom.description})"))
            form.lst_uom.choices = uoms_for_selection

        # Validate form entries upon submittal. If validated, send message:
        if form.validate_on_submit():
            # Initialize variables to be used in processing add request:
            msg_status = ""
            error_msg = ""

            # Check if user has selected a product image for the new product:
            if form.fil_product_image.data == None:
                msg_status = "Product image file not selected.  Please go back and select an image file for the new product."
            else:
                # Check if product name already exists in the db.  Capture feedback to relay to end user:
                prod_name_in_db = retrieve_from_database("get_prod_by_name", name=form.txt_name.data)
                if prod_name_in_db == {}:
                    error_msg = "An error has occurred. Product has not been added."
                elif prod_name_in_db != None:
                    msg_status = f"Product name '{form.txt_name.data}' already exists in the database.  Please go back and enter a unique product name."
                else:
                    # Add the new product record to the database.  Capture feedback to relay to end user:
                    if not update_database("add_prod", form=form):
                        error_msg = "An error has occurred. Product has not been added."
                    else:
                        msg_status = "Product has been successfully added."

            # Go to the user administration page and display the results of database update:
            return render_template("admin_product.html", trans_type="Add", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Go to the user administration page:
        return render_template("admin_product.html", trans_type="Add", form=form, error_msg=error_msg, msg_status=msg_status, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/add_product'", traceback.format_exc())

        # Go to the user administration page and display error details to the user:
        return render_template("admin_product.html", trans_type="Add", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Add UOM" web page:
@app.route('/add_uom',methods=["GET", "POST"])
@admin_only
def add_uom():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Instantiate an instance of the "AddOrEditUOMForm" class:
        form = AddOrEditUOMForm()

        # Validate form entries upon submittal. If validated, send message:
        if form.validate_on_submit():
            # Initialize variables to be used in processing add request:
            msg_status = ""
            error_msg = ""

            # Check if UOM already exists in the db.  Capture feedback to relay to end user:
            uom_in_db = retrieve_from_database("get_uom_by_code", code=form.txt_code.data)
            if uom_in_db == {}:
                error_msg = "An error has occurred. UOM has not been added."
            elif uom_in_db != None:
                msg_status = f"UOM '{form.txt_code.data}' already exists in the database.  Please go back and enter a unique UOM."
            else:
                # Add the new UOM record to the database.  Capture feedback to relay to end user:
                if not update_database("add_uom", form=form):
                    error_msg = "An error has occurred. UOM has not been added."
                else:
                    msg_status = "UOM has been successfully added."

            # Go to the UOM administration page and display the results of database update:
            return render_template("admin_uom.html", trans_type="Add", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Go to the UOM administration page:
        return render_template("admin_uom.html", trans_type="Add", form=form, msg_status=None, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/add_uom'", traceback.format_exc())

        # Go to the UOM administration page and display error details to the user:
        return render_template("admin_uom.html", trans_type="Add", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Add User" web page:
@app.route('/add_user',methods=["GET", "POST"])
@admin_only
def add_user():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Instantiate an instance of the "AddOrEditUserForm" class:
        form = AddOrEditUserForm()

        # Validate form entries upon submittal. If validated, send message:
        if form.validate_on_submit():
            # Initialize variables to be used in processing add request:
            msg_status = ""
            error_msg = ""

            # Check if user's username (e-mail address) already exists in the db.  Capture feedback to relay to end user:
            user_in_db = retrieve_from_database("get_user_by_username", username=form.txt_username.data)
            if user_in_db == {}:
                error_msg = "An error has occurred. User has not been added."
            elif user_in_db != None:
                msg_status = f"Username '{form.txt_username.data}' already exists in the database.  Please go back and enter a unique username (e-mail address)."
            else:
                # Add the new user record to the database.  Capture feedback to relay to end user:
                if not update_database("add_user", form=form):
                    error_msg = "An error has occurred. User has not been added."
                else:
                    msg_status = "User has been successfully added."

            # Go to the user administration page and display the results of database update:
            return render_template("admin_user.html", trans_type="Add", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Go to the user administration page:
        return render_template("admin_user.html", trans_type="Add", form=form, msg_status=None, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/add_user'", traceback.format_exc())

        # Go to the user administration page and display error details to the user:
        return render_template("admin_user.html", trans_type="Add", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Cart" web page:
@app.route('/cart')
@login_required
def cart():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track whether existing cart detail records were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        cart_details_count = 0

        # Initialize variables for total sales, tax, shipping, and grand total values across cart details:
        sum_sales_amt = 0
        sum_tax_amt = 0
        sum_ship_amt = 0
        sum_total_amt = 0

        # Get information on existing cart details in the database for the user currently logged in. Capture feedback to relay to end user:
        existing_cart_details = retrieve_from_database("get_cart_details_by_user_id_with_added_details", user_id=current_user.id)
        if existing_cart_details == {}:
            error_msg = f"An error has occurred. Cart details cannot be obtained at this time."
        elif existing_cart_details == []:
            error_msg = ""
        else:
            cart_details_count = len(existing_cart_details)  # Record count of existing cart details.

            # Total the sales_amt values across cart details:
            for detail in existing_cart_details:
                sum_sales_amt += detail["sales_amt"]

            # Calculate the totaL tax and shipping amounts applicable to the cart contents:
            sum_tax_amt = round(sum_sales_amt * RATE_SALES_TAX, 2)
            sum_ship_amt = round(sum_sales_amt * RATE_SHIPPING, 2)

            # Calculate the grand total amt applicable to the cart contents:
            sum_total_amt = sum_sales_amt + sum_tax_amt + sum_ship_amt

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "Cart" web page to render the results:
        return render_template("cart.html", cart_details=existing_cart_details, cart_details_count=cart_details_count, sum_sales_amt=sum_sales_amt, sum_tax_amt=sum_tax_amt, sum_ship_amt=sum_ship_amt, sum_total_amt=sum_total_amt, success=success,
                               error_msg=error_msg, active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/cart'", traceback.format_exc())

        # Go to the "Cart" web page and display error details to the user:
        return render_template("cart.html", error_msg=f"{traceback.format_exc()}", success=False,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for cart checkout:
@app.route('/checkout',methods=["GET", "POST"])
@login_required
def checkout():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track success of completing preliminary steps prior to checkout:
        msg_status = None
        success = False
        error_msg = ""

        # Get e-mail address and name of current user:
        customer = retrieve_from_database("get_user_by_id", user_id=current_user.id)
        if customer == {}:
            error_msg = f"An error has occurred. Checkout process cannot proceed."
        elif customer == None:
            error_msg = "User record was not retrieved. Checkout process cannot proceed."
        else:
            # Capture name and email address (username) from retrieved user record:
            customer_email = customer.username
            customer_name = customer.name

            # Get information on existing cart details in the database for the user currently logged in. Capture feedback to relay to end user:
            existing_cart_details = retrieve_from_database("get_cart_details_by_user_id_with_added_details", user_id=current_user.id)
            if existing_cart_details == {}:
                error_msg = f"An error has occurred. Cart details cannot be obtained at this time."
            elif existing_cart_details == []:
                error_msg = ""
            else:
                # For each cart detail, check to see if sufficient stock exists to fill desired product's
                # part of order (Stock may have been updated since item was last added to/updated in cart):
                for detail in existing_cart_details:
                    desired_product = retrieve_from_database("get_prod_by_id_with_uom", product_id = detail["product_id"])
                    if desired_product == {}:
                        error_msg = "Product record could not be retrieved to check stock level.  Checkout cannot proceed at this time."
                    elif desired_product == []:
                        error_msg = "A product record could not be retrieved to check stock level.  Checkout cannot proceed at this time."
                    else:
                        if desired_product[0]["qty_in_stock"] < detail["qty_ordered"]:
                            # If uom code = "EA", it doesn't need to be included in out-of-stock feedback to user.
                            if desired_product[0]["uom_name"] == "EA":
                                uom_desc = ""
                            else:
                                uom_desc = desired_product[0]["uom_desc"]
                            msg_status = f"Sorry, for product '{desired_product[0]["name"]}', we only have {desired_product[0]["qty_in_stock"]} {uom_desc.lower()} in stock.  Please go back and adjust quantity to buy."
                            break

        # If no anomalies have been detected with the preliminary checks above, indicate successful completion of same,
        # which would clear the way for proceeding with checkout completion:
        if msg_status == None and error_msg == "":
            success = True

        # If the preliminary steps above do not impede successful checkout, proceed with preparing the components of the
        # checkout instructions to pass along to Stripe for prompting payment:
        if success:
            # Initialize variable for total sales and shipping amts. across cart details:
            sum_sales_amt = 0
            sum_ship_amt = 0

            # Total the sales_amt values across cart details:
            for detail in existing_cart_details:
                sum_sales_amt += detail["sales_amt"]

            # Calculate the totaL shipping amount applicable to the cart contents:
            sum_ship_amt = round(sum_sales_amt * RATE_SHIPPING, 2)

            # Assign secret API key to the Stripe object:
            stripe.api_key = API_STRIPE_KEY_TEST_SECRET

            # Prepare the "tax_rate" component which will be part of the checkout instructions to Stripe:
            tax_rate = stripe.TaxRate.create(
                display_name='Tax',
                inclusive=False,
                percentage=int(RATE_SALES_TAX * 100),
                country='US',
                description='Tax amount',
            )

            # Using the retrieved contents of the "existing_cart_details" variable, prepare the "line_items"
            # component which will be part of the checkout instructions to stripe:
            line_items_list = []
            for detail in existing_cart_details:
                if detail["uom_name"] == "EA":
                    uom_desc = ""
                else:
                    uom_desc = f" ({detail["uom_desc"].lower()})"

                line_item_dict_to_append = {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f"{detail["product_name"]}{uom_desc}",
                        },
                        'unit_amount': int(detail["unit_price"] * 100),
                    },
                    'quantity': detail["qty_ordered"],
                    'tax_rates': [tax_rate.id]
                }

                line_items_list.append(line_item_dict_to_append)

            # Assign secret API key to the Stripe object:
            stripe.api_key = API_STRIPE_KEY_TEST_SECRET

            # Prepare the "tax_rate" component which will be part of the checkout instructions to Stripe:
            tax_rate = stripe.TaxRate.create(
                display_name='Tax',
                inclusive=False,
                percentage=RATE_SALES_TAX,
                country='US',
                description='Tax amount',
            )

            # Create and configure the Stripe checkout session:
            checkout_session = stripe.checkout.Session.create(
                line_items=line_items_list,
                shipping_options=[
                    {
                        'shipping_rate_data': {
                            'type': 'fixed_amount',
                            'fixed_amount': {
                                'amount': int(sum_ship_amt * 100),
                                'currency': 'usd',
                            },
                            'display_name': 'Standard Shipping',
                            'delivery_estimate': {
                                'minimum': {
                                    'unit': 'business_day',
                                    'value': 3,
                                },
                                'maximum': {
                                    'unit': 'business_day',
                                    'value': 5,
                                },
                            },
                        },
                    },
                ],
                mode='payment',
                invoice_creation={"enabled": True},
                customer_email=customer_email,
                metadata={
                    'customer_name': customer_name
                },
                success_url=SITE_DOMAIN + '/checkout_successful',
                cancel_url=SITE_DOMAIN + '/checkout_cancelled'
            )

            # Redirect to the Stripe checkout URL to complete the checkout process.  Upon successful payment
            # completion, site will redirect to the cart detail administration page to render feedback to user:
            return redirect(checkout_session.url, code=303)

        else:
            # Go to the cart detail administration page to render the results:
            return render_template("admin_cart_detail.html", success=success, msg_status=msg_status,
                                   error_msg=error_msg, active_product_categories=active_product_categories,
                                   active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:
        # Log error into system log:
        update_system_log("route: '/checkout'", traceback.format_exc())

        # Go to the cart detail administration page and display error details to the user:
        return render_template("admin_cart_detail.html", trans_type="Checkout", error_msg=f"{traceback.format_exc()}",
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Checkout cancelled" web page:
@app.route('/checkout_cancelled',methods=["GET", "POST"])
@login_required
def checkout_cancelled():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Prepare user feedback:
        msg_status = "Checkout has been cancelled."

        # Go to the cart detail administration web page to render user feedback:
        return render_template("admin_cart_detail.html", trans_type="Checkout",
                               msg_status=msg_status,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/checkout_cancelled'", traceback.format_exc())

        # Go to the cart detail administration page and display error details to the user:
        return render_template("admin_cart_detail.html", trans_type="Checkout", error_msg=f"{traceback.format_exc()}",
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Checkout successful" web page:
@app.route('/checkout_successful',methods=["GET", "POST"])
@login_required
def checkout_successful():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to be used in processing add request:
        msg_status = ""
        error_msg = ""

        # Create a new order, stamp it with today as the date ordered and paid, add the contents of the cart to that order,
        # and empty out the contents of the cart for the user currently logged in:
        new_order_id = update_database_with_trans("create_order", user_id=current_user.id)
        if new_order_id == False:
            error_msg = "While payment was successful, an error has occurred with creating and updating an order for this purchase.  Please contact this site's administrator as soon as possible."
        else:
            # Update cart detail count to 0 (for navigation bar), since successful order execution results in emptying of cart contents:
            cart_detail_count = 0

            # Prepare user feedback:
            msg_status = f"Checkout has been successful. The order ID for this purchase is '{new_order_id}'. Thank you for your order!"

        # Go to the cart detail administration web page to render user feedback:
        return render_template("admin_cart_detail.html", trans_type="Checkout Successful",
                               msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/checkout_successful'", traceback.format_exc())

        # Go to the cart detail administration page and display error details to the user:
        return render_template("admin_cart_detail.html", trans_type="Checkout", error_msg=f"{traceback.format_exc()}",
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Contact Us" web page:
@app.route('/contact',methods=["GET", "POST"])
def contact():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Instantiate an instance of the "ContactForm" class:
        form = ContactForm()

        # Validate form entries upon submittal. If validated, send message:
        if form.validate_on_submit():
            # Send message via e-mail:
            msg_status = email_from_contact_page(form)

            # Go to the "Contact Us" page and display the results of e-mail execution attempt:
            return render_template("contact.html", msg_status=msg_status, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # If a user is logged in, pre-populate the contact form with current user's name and e-mail address:
        if current_user.is_authenticated:
            form.txt_name.data = current_user.name
            form.txt_email.data = current_user.username

        # Go to the "Contact Us" page:
        return render_template("contact.html", form=form, msg_status=None, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/contact'", traceback.format_exc())

        # Go to the "Contact Us" web page and display error details to the user:
        return render_template("contact.html", error_msg=traceback.format_exc(), active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Delete Cart Detail" web page:
@app.route('/delete_cart_detail',methods=["GET", "POST"])
@login_required
def delete_cart_detail():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        cart_detail_id = request.args.get("cart_detail_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Get record to delete:
        record_to_delete = retrieve_from_database("get_cart_detail_by_id", cart_detail_id=cart_detail_id)
        if record_to_delete == {}:
            error_msg = "An error has occurred in retrieving the requested cart detail for deletion.  Deletion cannot proceed."
        elif record_to_delete == []:
            msg_status = "No matching cart detail was retrieved.  Deletion cannot proceed."
        else:
            record_to_delete = record_to_delete[0]

        # Go to the cart detail administration web page to confirm record deletion:
        return render_template("admin_cart_detail.html", trans_type="Delete", record_to_delete=record_to_delete, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_cart_detail'", traceback.format_exc())

        # Go to the cart detail administration page and display error details to the user:
        return render_template("admin_cart_detail.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Cart detail deletion result" web page:
@app.route('/delete_cart_detail_result',methods=["GET", "POST"])
@login_required
def delete_cart_detail_result():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        cart_detail_id = request.args.get("cart_detail_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Delete the cart detail record from the database.  Capture feedback to relay to end user:
        if not update_database("delete_cart_detail_by_id", cart_detail_id=cart_detail_id):
            error_msg = "An error has occurred in deleting the item from the cart."
        else:
            # Deduct cart detail count to update navigation bar in prep. for user feedback):
            cart_detail_count -= 1

            # Prepare successful-execution feedback for user:
            msg_status = "Item has been successfully deleted from cart."

        # Go to the cart detail administration page and display the results of database update:
        return render_template("admin_cart_detail.html", trans_type="Delete", msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_cart_detail_result'", traceback.format_exc())

        # Go to the cart detail administration page and display error details to the user:
        return render_template("admin_cart_detail.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Delete Product Category" web page:
@app.route('/delete_prod_cat',methods=["GET", "POST"])
@admin_only
def delete_prod_cat():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        prod_cat_id = request.args.get("prod_cat_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Get record to delete:
        record_to_delete = retrieve_from_database("get_prod_cat_by_id", prod_cat_id=prod_cat_id)
        if record_to_delete == {}:
            error_msg = "An error has occurred in retrieving the requested record for deletion.  Deletion cannot proceed."
        elif record_to_delete == []:
            msg_status = "No matching record was retrieved.  Deletion cannot proceed."

        # Go to the product-category administration web page to confirm record deletion:
        return render_template("admin_prod_cat.html", trans_type="Delete", record_to_delete=record_to_delete, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_prod_cat'", traceback.format_exc())

        # Go to the product-category administration page and display error details to the user:
        return render_template("admin_prod_cat.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Product category deletion result" web page:
@app.route('/delete_prod_cat_result',methods=["GET", "POST"])
@admin_only
def delete_prod_cat_result():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        prod_cat_id = request.args.get("prod_cat_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Validate deletion request prior to proceeding with deletion.  If no conflicts exist, deletion can proceed:
        validated, msg_status = validate_delete("prod_cat", prod_cat_id=prod_cat_id)
        if validated:
            # Delete the product category record from the database.  Capture feedback to relay to end user:
            if not update_database("delete_prod_cat_by_id", prod_cat_id=prod_cat_id):
                error_msg = "An error has occurred in deleting the product from the database."
            else:
                msg_status = "Record has been successfully deleted."

        else:
            msg_status = "Validation check failed. " + msg_status

        # Go to the product-category administration page and display the results of database update:
        return render_template("admin_prod_cat.html", trans_type="Delete", msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_prod_cat_result'", traceback.format_exc())

        # Go to the product-category administration page and display error details to the user:
        return render_template("admin_prod_cat.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Delete Product" web page:
@app.route('/delete_product',methods=["GET", "POST"])
@admin_only
def delete_product():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        product_id = request.args.get("product_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Get record to delete:
        record_to_delete = retrieve_from_database("get_prod_by_id", product_id=product_id)
        if record_to_delete == {}:
            error_msg = "An error has occurred in retrieving the requested record for deletion.  Deletion cannot proceed."
        elif record_to_delete == []:
            msg_status = "No matching record was retrieved.  Deletion cannot proceed."

        # Go to the product administration web page to confirm record deletion:
        return render_template("admin_product.html", trans_type="Delete", record_to_delete=record_to_delete, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_product'", traceback.format_exc())

        # Go to the product administration page and display error details to the user:
        return render_template("admin_product.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Product deletion result" web page:
@app.route('/delete_product_result',methods=["GET", "POST"])
@admin_only
def delete_product_result():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        product_id = request.args.get("product_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Validate deletion request prior to proceeding with deletion.  If no conflicts exist, deletion can proceed:
        validated, msg_status = validate_delete("product", product_id=product_id)
        if validated:
            # Delete the product record from the database.  Capture feedback to relay to end user:
            if not update_database("delete_prod_by_id", product_id=product_id):
                error_msg = "An error has occurred in deleting the product from the database."
            else:
                msg_status = "Record has been successfully deleted."

        else:
            msg_status = "Validation check failed. " + msg_status

        # Go to the product administration page and display the results of database update:
        return render_template("admin_product.html", trans_type="Delete", msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_product_result'", traceback.format_exc())

        # Go to the product administration page and display error details to the user:
        return render_template("admin_product.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Delete UOM" web page:
@app.route('/delete_uom',methods=["GET", "POST"])
@admin_only
def delete_uom():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        uom_id = request.args.get("uom_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Get record to delete:
        record_to_delete = retrieve_from_database("get_uom_by_id", uom_id=uom_id)
        if record_to_delete == {}:
            error_msg = "An error has occurred in retrieving the requested record for deletion.  Deletion cannot proceed."
        elif record_to_delete == []:
            msg_status = "No matching record was retrieved.  Deletion cannot proceed."

        # Go to the UOM administration web page to confirm record deletion:
        return render_template("admin_uom.html", trans_type="Delete", record_to_delete=record_to_delete, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_uom'", traceback.format_exc())

        # Go to the UOM administration page and display error details to the user:
        return render_template("admin_uom.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "UOM deletion result" web page:
@app.route('/delete_uom_result',methods=["GET", "POST"])
@admin_only
def delete_uom_result():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        uom_id = request.args.get("uom_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Validate deletion request prior to proceeding with deletion.  If no conflicts exist, deletion can proceed:
        validated, msg_status = validate_delete("uom", uom_id=uom_id)
        if validated:
            # Delete the UOM record from the database.  Capture feedback to relay to end user:
            if not update_database("delete_uom_by_id", uom_id=uom_id):
                error_msg = "An error has occurred in deleting the UOM from the database."
            else:
                msg_status = "Record has been successfully deleted."

        else:
            msg_status = "Validation check failed. " + msg_status

        # Go to the UOM administration page and display the results of database update:
        return render_template("admin_uom.html", trans_type="Delete", msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_uom_result'", traceback.format_exc())

        # Go to the UOM administration page and display error details to the user:
        return render_template("admin_uom.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Delete User" web page:
@app.route('/delete_user',methods=["GET", "POST"])
@admin_only
def delete_user():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        user_id = request.args.get("user_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Get record to delete:
        record_to_delete = retrieve_from_database("get_user_by_id", user_id=user_id)
        if record_to_delete == {}:
            error_msg = "An error has occurred in retrieving the requested record for deletion.  Deletion cannot proceed."
        elif record_to_delete == []:
            msg_status = "No matching record was retrieved.  Deletion cannot proceed."

        # Go to the user administration web page to confirm record deletion:
        return render_template("admin_user.html", trans_type="Delete", record_to_delete=record_to_delete, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_user'", traceback.format_exc())

        # Go to the user administration page and display error details to the user:
        return render_template("admin_user.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "User deletion result" web page:
@app.route('/delete_user_result',methods=["GET", "POST"])
@admin_only
def delete_user_result():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        user_id = request.args.get("user_id",None)

        # Initialize variables to be used in processing deletion request:
        msg_status = ""
        error_msg = ""

        # Validate deletion request prior to proceeding with deletion.  If no conflicts exist, deletion can proceed:
        validated, msg_status = validate_delete("user", user_id=user_id)
        if validated:
            # Delete the user record from the database.  Capture feedback to relay to end user:
            if not update_database("delete_user_by_id", user_id=user_id):
                error_msg = "An error has occurred in deleting the user from the database."
            else:
                msg_status = "Record has been successfully deleted."

        else:
            msg_status = "Validation check failed. " + msg_status

        # Go to the user administration page and display the results of database update:
        return render_template("admin_user.html", trans_type="Delete", msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/delete_user_result'", traceback.format_exc())

        # Go to the user administration page and display error details to the user:
        return render_template("admin_user.html", trans_type="Delete", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Edit Cart Detail" web page:
@app.route('/edit_cart_detail', methods=["GET", "POST"])
@login_required
def edit_cart_detail():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameters passed to this route:
        cart_detail_id = request.args.get("cart_detail_id", None)
        product_id = request.args.get("product_id", None)

        # Instantiate an instance of the "EditCartDetailForm" class:
        form = EditCartDetailForm()

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            msg_status = ""
            error_msg = ""
            update_db = False

            # Retrieve desired product record from database:
            desired_product = retrieve_from_database("get_prod_by_id_with_uom", product_id=product_id)
            if desired_product == {}:
                error_msg = "An error has occurred. Cart detail cannot be edited at this time."
            elif desired_product == []:
                msg_status = "No matching product was retrieved.  Cart detail cannot be edited at this time."
            else:
                # Check if sufficient stock of desired product exists in database to cover the (updated) ordered quantity of same:
                if form.txt_qty_ordered.data > desired_product[0]["qty_in_stock"]:  # Insufficient stock.
                    # If uom code = "EA", it doesn't need to be included in out-of-stock feedback to user.
                    if desired_product[0]["uom_name"] == "EA":
                        uom_desc = ""
                    else:
                        uom_desc = desired_product[0]["uom_desc"]
                    msg_status = f"Sorry, we only have {desired_product[0]["qty_in_stock"]} {uom_desc.lower()} in stock.  Please go back and adjust quantity to buy."
                else:
                    update_db = True

            # If database update can proceed, then do so:
            if update_db:
                # Update the database to edit cart detail.  Capture feedback to relay to end user:
                if not update_database("edit_prod_in_cart", cart_detail_id=cart_detail_id,
                                       qty_updated=form.txt_qty_ordered.data):
                    error_msg = "An error has occurred. Cart has not been updated."
                else:
                    msg_status = "Cart detail has been successfully updated."

            # Go to the cart detail administration page and display the results of database update:
            return render_template("admin_cart_detail.html", msg_status=msg_status, error_msg=error_msg,
                                   active_product_categories=active_product_categories,
                                   active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to be used in processing edit request:
        msg_status = ""
        error_msg = ""

        # Get record to edit:
        record_to_edit = retrieve_from_database("get_cart_detail_by_id", cart_detail_id=cart_detail_id)
        if record_to_edit == {}:
            error_msg = "An error has occurred in retrieving the requested record for editing.  Edit cannot proceed."
        elif record_to_edit == []:
            msg_status = "No matching record was retrieved.  Edit cannot proceed."
        else:
            record_to_edit = record_to_edit[0]

            # Populate the form with the retrieved record's contents:
            form.txt_prod_name.data = str(record_to_edit["product_name"])
            form.txt_qty_ordered.data = record_to_edit["qty_ordered"]
            form.lst_uom_name.data = str(record_to_edit["uom_name"])
            form.txt_unit_price.data = record_to_edit["unit_price"]

        # Go to the cart detail administration web page to confirm record updating:
        return render_template("admin_cart_detail.html", trans_type="Edit", form=form, msg_status=msg_status,
                               error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/edit_cart_detail'", traceback.format_exc())

        # Go to the cart detail administration page and display error details to the user:
        return render_template("admin_cart_detail.html", trans_type="Edit", error_msg=f"{traceback.format_exc()}",
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Edit Order" web page:
@app.route('/edit_order',methods=["GET", "POST"])
@admin_only
def edit_order():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameters passed to this route:
        order_id = request.args.get("order_id", None)

        # Instantiate an instance of the "EditOrderForm" class:
        form = EditOrderForm()

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            msg_status = ""
            error_msg = ""

            # Update the database to edit order (user-editable fields only).  Capture feedback to relay to end user:
            if not update_database("edit_order", order_id=order_id, form=form):
                error_msg = "An error has occurred. Order has not been updated."
            else:
                msg_status = "Order has been successfully updated."

            # Go to the order administration page and display the results of database update:
            return render_template("admin_order.html", trans_type="Edit", msg_status=msg_status, error_msg=error_msg,
                                   active_product_categories=active_product_categories,
                                   active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to be used in processing edit request:
        msg_status = ""
        error_msg = ""

        # Get record to edit:
        record_to_edit = retrieve_from_database("get_order_by_order_id_with_added_details", order_id=order_id)
        if record_to_edit == {}:
            error_msg = "An error has occurred in retrieving the requested record for editing.  Edit cannot proceed."
        elif record_to_edit == []:
            msg_status = "No matching record was retrieved.  Edit cannot proceed."
        else:
            record_to_edit = record_to_edit[0]

            # Populate the form with the retrieved record's contents:
            form.txt_order_id.data = record_to_edit["order_id"]
            form.txt_date_ordered.data = record_to_edit["date_ordered"]
            form.txt_date_paid.data = record_to_edit["date_paid"]
            form.txt_date_shipped.data = record_to_edit["date_shipped"]
            form.txt_user_name.data = record_to_edit["user_name"]
            form.txt_user_username.data = record_to_edit["user_username"]
            form.txt_notes.data = record_to_edit["notes"]

        # Go to the order administration web page to confirm record updating:
        return render_template("admin_order.html", trans_type="Edit", form=form, msg_status=msg_status,
                               error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/edit_order'", traceback.format_exc())

        # Go to the order administration page and display error details to the user:
        return render_template("admin_order.html", trans_type="Edit", error_msg=f"{traceback.format_exc()}",
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Edit Product Category" web page:
@app.route('/edit_prod_cat',methods=["GET", "POST"])
@admin_only
def edit_prod_cat():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        prod_cat_id = request.args.get("prod_cat_id",None)

        # Instantiate an instance of the "AddOrEditProductCategoryForm" class:
        form = AddOrEditProductCategoryForm()

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            msg_status = ""
            error_msg = ""
            update_db = False

            # Check if name of product category already exists in the db. Capture feedback to relay to end user:
            prod_cat_name_in_db = retrieve_from_database("get_prod_cat_by_name", prod_cat_name=form.txt_name.data)
            if prod_cat_name_in_db == {}:
                msg_status = "An error has occurred. Edit cannot proceed."
            else:
                if prod_cat_name_in_db != None:
                    if prod_cat_name_in_db.category_id != int(prod_cat_id):  # Product category name exists in another record other than the one being edited.
                        msg_status = f"Product category '{form.txt_name.data}' already exists in the database.  Please go back and enter a unique product category."
                    else:
                        # Indicate that database update can proceed:
                        update_db = True
                else:
                    # Indicate that database update can proceed:
                    update_db = True

                # If database update can proceed, then do so:
                if update_db:
                    # Update the desired product category record in the database.  Capture feedback to relay to end user:
                    if not update_database("edit_prod_cat", form=form, prod_cat_id=prod_cat_id):
                        error_msg = "An error has occurred. Product category has not been edited."
                    else:
                        msg_status = "Product category has been successfully edited."

            # Go to the product-category administration page and display the results of database update:
            return render_template("admin_prod_cat.html", trans_type="Edit", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to be used in processing edit request:
        msg_status = ""
        error_msg = ""

        # Get record to edit:
        record_to_edit = retrieve_from_database("get_prod_cat_by_id", prod_cat_id=prod_cat_id)
        if record_to_edit == {}:
            error_msg = "An error has occurred in retrieving the requested record for editing.  Edit cannot proceed."
        elif record_to_edit == []:
            msg_status = "No matching record was retrieved.  Edit cannot proceed."
        else:
            # Populate the form with the retrieved record's contents:
            form.txt_name.data = record_to_edit.name
            form.txt_description.data = record_to_edit.description
            form.chk_active.data = record_to_edit.active

        # Go to the product-category administration web page to confirm record updating:
        return render_template("admin_prod_cat.html", trans_type="Edit", form=form, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/edit_prod_cat'", traceback.format_exc())

        # Go to the product-category administration page and display error details to the user:
        return render_template("admin_prod_cat.html", trans_type="Edit", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Edit Product" web page:
@app.route('/edit_product',methods=["GET", "POST"])
@admin_only
def edit_product():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        product_id = request.args.get("product_id",None)

        # Instantiate an instance of the "AddOrEditProductForm" class:
        form = AddOrEditProductForm()

        # Initialize variables to be used in capturing anomalies encountered during population of selection lists on the form:
        msg_status = None
        error_msg = ""

        # Populate the product category selection list on the form:
        prod_cats_for_selection = []
        prod_cats, prod_cat_count = get_product_categories_for_selection()
        if prod_cats == {}:
            error_msg = "An error has occurred in populating the Product Category selection list."
        elif prod_cat_count == 0:
            msg_status = "No selections are available for Product Category."
        else:
            for prod_cat in prod_cats:
                prod_cats_for_selection.append((prod_cat.category_id, f"{prod_cat.name} ({prod_cat.description})"))
            form.lst_prod_cat.choices = prod_cats_for_selection

        # Populate the units of measure selection list on the form:
        uoms_for_selection = []
        uoms, uom_count = get_uoms_for_selection()
        if uoms == {}:
            error_msg = "An error has occurred in populating the Unit of Measure (UOM) selection list."
        elif uom_count == 0:
            msg_status = "No selections are available for Unit of Measure (UOM)."
        else:
            for uom in uoms:
                uoms_for_selection.append((uom.uom_id, f"{uom.code} ({uom.description})"))
            form.lst_uom.choices = uoms_for_selection

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            msg_status = ""
            error_msg = ""
            update_db = False

            # Check if product name already exists in the db. Capture feedback to relay to end user:
            prod_name_in_db = retrieve_from_database("get_prod_by_name", name=form.txt_name.data)
            if prod_name_in_db == {}:
                msg_status = "An error has occurred. Edit cannot proceed."
            else:
                if prod_name_in_db != None:
                    if prod_name_in_db.product_id != int(product_id):  # Product name exists in another record other than the one being edited.
                        msg_status = f"Product name '{form.txt_name.data}' already exists in the database.  Please go back and enter a unique product name."
                    else:
                        # Indicate that database update can proceed:
                        update_db = True
                else:
                    # Indicate that database update can proceed:
                    update_db = True

                # If database update can proceed, then do so:
                if update_db:
                    # Update the desired product record in the database.  If update involves a unit price change,
                    # then update all cart details associated with that product to reflect updated unit price.
                    # Capture feedback to relay to end user:
                    if not update_database_with_trans("edit_product", form=form, product_id=product_id):
                        error_msg = "An error has occurred. Product record has not been edited."
                    else:
                        msg_status = "Product record has been successfully edited."

            # Go to the product administration page and display the results of database update:
            return render_template("admin_product.html", trans_type="Edit", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to be used in processing edit request:
        msg_status = ""
        error_msg = ""

        # Get record to edit:
        record_to_edit = retrieve_from_database("get_prod_by_id", product_id=product_id)
        if record_to_edit == {}:
            error_msg = "An error has occurred in retrieving the requested record for editing.  Edit cannot proceed."
        elif record_to_edit == []:
            msg_status = "No matching record was retrieved.  Edit cannot proceed."
        else:
            # Populate the form with the retrieved record's contents:
            form.txt_name.data = record_to_edit.name
            form.lst_prod_cat.data = str(record_to_edit.category_id)
            form.txt_description.data = record_to_edit.description
            form.txt_qty_in_stock.data = record_to_edit.qty_in_stock
            form.lst_uom.data = str(record_to_edit.uom_id)
            form.txt_unit_price_regular.data = record_to_edit.unit_price_regular
            form.txt_unit_price_discounted.data = record_to_edit.unit_price_discounted
            form.txt_product_image.data = record_to_edit.product_image
            form.chk_active.data = record_to_edit.active

        # Go to the product administration web page to confirm record updating:
        return render_template("admin_product.html", trans_type="Edit", form=form, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/edit_product'", traceback.format_exc())

        # Go to the product administration page and display error details to the user:
        return render_template("admin_product.html", trans_type="Edit", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Edit UOM" web page:
@app.route('/edit_uom',methods=["GET", "POST"])
@admin_only
def edit_uom():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        uom_id = request.args.get("uom_id",None)

        # Instantiate an instance of the "AddOrEditUOMForm" class:
        form = AddOrEditUOMForm()

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            msg_status = ""
            error_msg = ""
            update_db = False

            # Check if UOM already exists in the db. Capture feedback to relay to end user:
            uom_in_db = retrieve_from_database("get_uom_by_code", code=form.txt_code.data)
            if uom_in_db == {}:
                msg_status = "An error has occurred. Edit cannot proceed."
            else:
                if uom_in_db != None:
                    if uom_in_db.uom_id != int(uom_id):  # UOM exists in another record other than the one being edited.
                        msg_status = f"UOM '{form.txt_code.data}' already exists in the database.  Please go back and enter a unique UOM."
                    else:
                        # Indicate that database update can proceed:
                        update_db = True
                else:
                    # Indicate that database update can proceed:
                    update_db = True

                # If database update can proceed, then do so:
                if update_db:
                    # Update the desired UOM record in the database.  Capture feedback to relay to end user:
                    if not update_database("edit_uom", form=form, uom_id=uom_id):
                        error_msg = "An error has occurred. UOM has not been edited."
                    else:
                        msg_status = "UOM has been successfully edited."

            # Go to the UOM administration page and display the results of database update:
            return render_template("admin_uom.html", trans_type="Edit", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to be used in processing edit request:
        msg_status = ""
        error_msg = ""

        # Get record to edit:
        record_to_edit = retrieve_from_database("get_uom_by_id", uom_id=uom_id)
        if record_to_edit == {}:
            error_msg = "An error has occurred in retrieving the requested record for editing.  Edit cannot proceed."
        elif record_to_edit == []:
            msg_status = "No matching record was retrieved.  Edit cannot proceed."
        else:
            # Populate the form with the retrieved record's contents:
            form.txt_code.data = record_to_edit.code
            form.txt_description.data = record_to_edit.description

        # Go to the UOM administration web page to confirm record updating:
        return render_template("admin_uom.html", trans_type="Edit", form=form, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/edit_uom'", traceback.format_exc())

        # Go to the UOM administration page and display error details to the user:
        return render_template("admin_uom.html", trans_type="Edit", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Edit User" web page:
@app.route('/edit_user',methods=["GET", "POST"])
@admin_only
def edit_user():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        user_id = request.args.get("user_id",None)

        # Instantiate an instance of the "AddOrEditUserForm" class:
        form = AddOrEditUserForm()

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            msg_status = ""
            error_msg = ""
            update_db = False

            # Check if username (e-mail address) already exists in the db. Capture feedback to relay to end user:
            user_in_db = retrieve_from_database("get_user_by_username", username=form.txt_username.data)
            if user_in_db == {}:
                msg_status = "An error has occurred. Edit cannot proceed."
            else:
                if user_in_db != None:
                    if user_in_db.id != int(user_id):  # Username exists in another record other than the one being edited.
                        msg_status = f"Username '{form.txt_username.data}' already exists in the database.  Please go back and enter a unique username (e-mail address)."
                    else:
                        # Indicate that database update can proceed:
                        update_db = True
                else:
                    # Indicate that database update can proceed:
                    update_db = True

                # If database update can proceed, then do so:
                if update_db:
                    # Update the desired UOM record in the database.  Capture feedback to relay to end user:
                    if not update_database("edit_user", form=form, user_id=user_id):
                        error_msg = "An error has occurred. User record has not been edited."
                    else:
                        msg_status = "User record has been successfully edited."

            # Go to the user administration page and display the results of database update:
            return render_template("admin_user.html", trans_type="Edit", msg_status=msg_status, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to be used in processing edit request:
        msg_status = ""
        error_msg = ""

        # Get record to edit:
        record_to_edit = retrieve_from_database("get_user_by_id", user_id=user_id)
        if record_to_edit == {}:
            error_msg = "An error has occurred in retrieving the requested record for editing.  Edit cannot proceed."
        elif record_to_edit == []:
            msg_status = "No matching record was retrieved.  Edit cannot proceed."
        else:
            # Populate the form with the retrieved record's contents:
            form.txt_name.data = record_to_edit.name
            form.txt_username.data = record_to_edit.username
            form.txt_password.data = record_to_edit.password
            form.chk_active.data = record_to_edit.active

        # Go to the user administration web page to confirm record updating:
        return render_template("admin_user.html", trans_type="Edit", form=form, msg_status=msg_status, error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/edit_user'", traceback.format_exc())

        # Go to the user administration page and display error details to the user:
        return render_template("admin_user.html", trans_type="Edit", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "user login: web page:
@app.route('/login', methods=['GET', 'POST'])
def login():
    global db, admin

    try:
        # Instantiate an instance of the "LoginForm" class:
        form = LoginForm()

        if form.validate_on_submit():
            # Initialize variables to be used in processing registration request:
            msg_status = ""
            error_msg = ""

            # Capture the supplied e-mail address and password:
            username = form.txt_username.data
            password = form.txt_password.data

            # Check if user account exists under the supplied e-mail address:
            user = retrieve_from_database("get_user_by_username", username=username)
            if user != None: # Account exists under the supplied e-mail address
                # Check if user account is active:
                if user.active == 1:
                    # Check if supplied password matches the salted/hashed password for that account in the db:
                    if check_password_hash(user.password, password): # Passwords match
                        # Capture if user is an admin:
                        if user.id == 1:
                            admin = True
                        else:
                            admin = False

                        # Log user in:
                        login_user(user)

                        # Go to home page:
                        return redirect(url_for('home'))

                    else:  # Password is incorrect.
                        msg_status = "Invalid password."

                else:  # User account is not active.
                    msg_status = "Account is disabled.  Please contact us for assistance."

            else: # Account does NOT exist under the supplied username (e-mail address).
                msg_status = f"No account exists under username (e-mail) '{username}'."

            # Go to the login page and render feedback to user:
            return render_template('login.html', form=form, msg_status=msg_status, current_user=current_user)

        # Go to the login page:
        return render_template('login.html', form=form, current_user=current_user)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/login'", traceback.format_exc())

        # Go to the login page and display error details to the user:
        return render_template("login.html", error_msg=f"{traceback.format_exc()}")


# Configure route for user-logout workflow:
@app.route('/logout')
def logout():
    global admin

    try:
        # Log user out:
        logout_user()

        # Reset the admin variable:
        admin = False

        # Go to the home page:
        return redirect(url_for('home'))

    except:  # An error has occurred.
        # Reset the admin variable:
        admin = False

        # Log error into system log file:
        update_system_log("route: '/logout'", traceback.format_exc())

        # Go to the registration page and display error details to the user:
        return render_template("logout.html", error_msg=f"{traceback.format_exc()}")


# Configure route for "Orders" web page:
@app.route('/orders')
@login_required
def orders():
    global admin
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track whether existing order records were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        order_count = 0

        # Get information on existing orders in the database for the user currently logged in. If user is the admin,
        # get all orders across all users. Capture feedback to relay to end user:
        existing_orders = retrieve_from_database("get_orders_by_user_id_with_added_details", user_id=current_user.id)
        if existing_orders == {}:
            error_msg = f"An error has occurred. Orders cannot be obtained at this time."
        elif existing_orders == []:
            error_msg = ""
        else:
            order_count = len(existing_orders)  # Record count of existing orders.

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "Orders" web page to render the results:
        return render_template("orders.html", orders=existing_orders, order_count=order_count, success=success,
                               error_msg=error_msg, active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/orders'", traceback.format_exc())

        # Go to the "Orders" web page and display error details to the user:
        return render_template("orders.html", error_msg=f"{traceback.format_exc()}", success=False,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Product Categories" web page:
@app.route('/product_categories')
@admin_only
def product_categories():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track whether existing product categories were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        cat_count = 0

        # Get information on existing product categories in the database. Capture feedback to relay to end user:
        existing_categories = retrieve_from_database("get_all_product_categories")
        if existing_categories == {}:
            error_msg = f"An error has occurred. Product category information cannot be obtained at this time."
        elif existing_categories == []:
            error_msg = ""
        else:
            cat_count = len(existing_categories)  # Record count of existing product categories.

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "Product Categories" page:
        return render_template("product_categories.html", categories=existing_categories, cat_count=cat_count, success=success, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/product_categories'", traceback.format_exc())

        # Go to the "Product Categories" page and display error details to the user:
        return render_template("product_categories.html", error_msg=f"{traceback.format_exc()}", active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Products" web page:
@app.route('/products')
@admin_only
def products():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track whether existing product records were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        prod_count = 0

        # Get information on existing products in the database. Capture feedback to relay to end user:
        existing_products = retrieve_from_database("get_all_products")
        if existing_products == {}:
            error_msg = f"An error has occurred. Product information cannot be obtained at this time."
        elif existing_products == []:
            error_msg = ""
        else:
            prod_count = len(existing_products)  # Record count of existing products.

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "Products" web page to render the results:
        return render_template("products.html", products=existing_products, prod_count=prod_count, success=success,
                               error_msg=error_msg, active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/products'", traceback.format_exc())

        # Go to the "Products" web page and display error details to the user:
        return render_template("products.html", error_msg=f"{traceback.format_exc()}", success=False,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "new user registration" web page:
@app.route('/register', methods=["GET", "POST"])
def register():
    global admin

    try:
        # Instantiate an instance of the "RegisterForm" class:
        form = RegisterForm()

        # Validate form entries upon submittal.  If validated, add user to the db and inform user of result:
        if form.validate_on_submit():
            # Initialize variables to be used in processing registration request:
            msg_status = ""
            error_msg = ""

            # Store supplied name and e-mail address into variables:
            name = form.txt_name.data
            username = form.txt_username.data

            # Check if an account already exists under the supplied email address.
            user = retrieve_from_database("get_user_by_username", username=username)
            if user != None:  # Account already exists.
                msg_status = f"An account already exists under username (e-mail address) '{username}'. Please go back and enter a unique username (e-mail address)."
            else:
                # Create a record in "users" table in the database.  Capture feedback to relay to the end user:
                if not update_database("add_user_via_registration", form=form):
                    error_msg = "An error has occurred.  New user has not been registered."
                else:
                    # Retrieve the newly-created user record to confirm whether user is an admin or not:
                    new_user = retrieve_from_database("get_user_by_username", username=username)
                    if new_user == {} or new_user == None:
                        error_msg = "An error has occurred.  User has been registered, but login cannot proceed at this time."
                    else:
                        # Capture if user is an admin:
                        if new_user.id == 1:
                            admin = True
                        else:
                            admin = False

                        # Log in and authenticate the user upon registering:
                        login_user(new_user)

                # Prepare feedback to user to indicate that registration was successful:
                msg_status = f"Registration was successful.  Welcome, {name}!  You are now logged in."

            # Go to the registration page and display the results of registration attempt:
            return render_template("register.html", msg_status=msg_status, error_msg=error_msg, cart_detail_count=0)

        # Go to the registration page:
        return render_template("register.html", form=form)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/register'", traceback.format_exc())

        # Go to the registration page and display error details to the user:
        return render_template("register.html", error_msg=f"{traceback.format_exc()}")


# Configure route for "Units of Measure" web page:
@app.route('/uom')
@admin_only
def uom():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track whether existing units of measure were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        uom_count = 0

        # Get information on existing units of measure in the database. Capture feedback to relay to end user:
        existing_uoms = retrieve_from_database("get_all_uoms")
        if existing_uoms == {}:
            error_msg = f"An error has occurred. Unit-of-measure information cannot be obtained at this time."
        elif existing_uoms == []:
            error_msg = ""
        else:
            uom_count = len(existing_uoms)  # Record count of existing units of measure.

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "Units of Measure" page:
        return render_template("uom.html", uoms=existing_uoms, uom_count=uom_count, success=success, error_msg=error_msg, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/uom'", traceback.format_exc())

        # Go to the "Units of Measure" page and display error details to the user:
        return render_template("uom.html", error_msg=f"{traceback.format_exc()}", success=False, active_product_categories=active_product_categories, active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "Users" web page:
@app.route('/users')
@admin_only
def users():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Initialize variables to track whether existing user records were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        user_count = 0

        # Get information on existing users in the database. Capture feedback to relay to end user:
        existing_users = retrieve_from_database("get_all_users")
        if existing_users == {}:
            error_msg = f"An error has occurred. User information cannot be obtained at this time."
        elif existing_users == []:
            error_msg = ""
        else:
            user_count = len(existing_users)  # Record count of existing users.

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "Users" web page to render the results:
        return render_template("users.html", users=existing_users, user_count=user_count, success=success,
                               error_msg=error_msg, active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/users'", traceback.format_exc())

        # Go to the "Users" web page and display error details to the user:
        return render_template("users.html", error_msg=f"{traceback.format_exc()}", success=False,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "View Order" web page:
@app.route('/view_order',methods=["GET", "POST"])
@login_required
def view_order():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        order_id = request.args.get("order_id",None)

        # Initialize variables to track whether existing order detail records were successfully obtained or if an error has occurred:
        success = False
        error_msg = ""
        order_details_count = 0

        # Retrieve desired order record from the database. Capture feedback to relay to end user:
        desired_order = retrieve_from_database("get_order_by_order_id_with_added_details", order_id=order_id)
        if desired_order == {}:
            error_msg = f"An error has occurred. Order details cannot be obtained at this time."
        elif desired_order == []:
            error_msg = "No matching order record was retrieved.  Order details cannot be obtained at this time."
        else:
            desired_order = desired_order[0]

            # Get information on existing order details in the database. Capture feedback to relay to end user:
            existing_order_details = retrieve_from_database("get_order_details_by_order_id", order_id=int(order_id))
            if existing_order_details == {}:
                error_msg = f"An error has occurred. Order details cannot be obtained at this time."
            elif existing_order_details == []:
                error_msg = ""
            else:
                order_details_count = len(existing_order_details)  # Record count of existing order details.

                # Indicate that record retrieval has been successfully executed:
                success = True

        # Go to the "view order" web page to render the results:
        return render_template("view_order.html", order=desired_order, order_details=existing_order_details, order_details_count=order_details_count, success=success,
                               error_msg=error_msg, active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("route: '/view_order'", traceback.format_exc())

        # Go to the "Cart" web page and display error details to the user:
        return render_template("view_order.html", error_msg=f"{traceback.format_exc()}", success=False,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# Configure route for "View Product" web page:
@app.route('/view_product',methods=["GET", "POST"])
@login_required
def view_product():
    try:
        # Retrieve info. on active product categories (for population of the navigation bar):
        active_product_categories, active_prod_cat_count = get_active_product_categories()

        # Retrieve # of items currently in cart (for population of the navigation bar):
        cart_detail_count = get_cart_detail_count()

        # Capture parameter passed to this route:
        product_id = request.args.get("product_id",None)

        # Instantiate an instance of the "AddProductToCartForm" class:
        form = AddProductToCartForm()

        # If form-level validation has passed, perform additional processing:
        if form.validate_on_submit():
            # Initialize variables required as part of processing requested transaction:
            successful_cart_update = False
            msg_status = ""
            error_msg = ""
            update_db = False
            update_type = ""

            # Retrieve desired product record from database:
            desired_product = retrieve_from_database("get_prod_by_id_with_uom", product_id=product_id)
            if desired_product == {}:
                error_msg = "An error has occurred. Product cannot be added to cart at this time."
            elif desired_product == []:
                msg_status = "No matching product was retrieved.  Product cannot be added to cart at this time."
            else:
                # Check if sufficient stock of desired product exists in database to cover the ordered quantity of same:
                if form.txt_qty_ordered.data > desired_product[0]["qty_in_stock"]:  # Insufficient stock.
                    # If uom code = "EA", it doesn't need to be included in out-of-stock feedback to user.
                    if desired_product[0]["uom_name"] == "EA":
                        uom_desc = ""
                    else:
                        uom_desc = desired_product[0]["uom_desc"]
                    msg_status = f"Sorry, we only have {desired_product[0]["qty_in_stock"]} {uom_desc.lower()} in stock.  Please go back and adjust quantity to buy."
                else:
                    # Check if item is already in cart for the user currently logged in.  If yes, then add qty ordered of desired product to existing cart-detail record for that product:
                    cart_detail_with_prod = retrieve_from_database("get_cart_detail_by_user_id_and_prod_id", user_id=current_user.id, product_id=product_id)
                    if cart_detail_with_prod == {}:
                        error_msg = "An error has occurred. Product cannot be added to cart at this time."
                    elif cart_detail_with_prod == None:
                        update_type = "Add"
                        update_db = True
                    else:
                        update_type = "Edit"
                        update_db = True

            # If database update can proceed, then do so:
            if update_db:
                # Update the database to add desired product to cart for the user currently logged in.  Capture feedback to relay to end user:
                if update_type == "Add":
                    if not update_database("add_prod_to_cart", form=form, user_id=current_user.id, product=desired_product[0]):
                        error_msg = "An error has occurred. Product has not been added to cart."
                    else:
                        # Update cart detail count (to update navigation bar in prep. for user feedback:
                        cart_detail_count += 1

                        # Indicate that cart update has been successful:
                        msg_status = ""
                        successful_cart_update = True

                elif update_type == "Edit":
                    if not update_database("edit_prod_in_cart", cart_detail_id=cart_detail_with_prod.cart_detail_id, qty_updated=cart_detail_with_prod.qty_ordered + form.txt_qty_ordered.data):
                        error_msg = "An error has occurred. Cart has not been updated."
                    else:
                        # If uom code = "EA", it doesn't need to be included in out-of-stock feedback to user.
                        if desired_product[0]["uom_name"] == "EA":
                            uom_desc = ""
                        else:
                            uom_desc = desired_product[0]["uom_desc"]
                        msg_status = f"Since {cart_detail_with_prod.qty_ordered} {uom_desc.lower()} was already in cart, quantity has been updated to add {form.txt_qty_ordered.data} {uom_desc.lower()} to existing cart entry."
                        successful_cart_update = True

            # If item was successfully added and no feedback to user is required, go to cart:
            if successful_cart_update and msg_status == "":
                return redirect(url_for("cart"))
            else:
                # Go to the "View Product" page and display feedback to user:
                return render_template("view_product.html", msg_status=msg_status, error_msg=error_msg, successful_cart_update=successful_cart_update,
                                       active_product_categories=active_product_categories,
                                       active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

        # Initialize variables to track whether existing product record was successfully obtained or if an error has occurred:
        success = False
        error_msg = ""

        # Retrieve desired product record from the database. Capture feedback to relay to end user:
        desired_product = retrieve_from_database("get_prod_by_id_with_uom", product_id=product_id)
        if desired_product == {}:
            error_msg = f"An error has occurred. Product information cannot be obtained at this time."
        elif desired_product == []:
            error_msg = "No matching product record was retrieved.  Purchase of this product cannot be transacted at this time."
        else:
            # Include the UOM for the desired product as part of the "add to cart" form:
            form.txt_qty_ordered.label.text = "Qty. to Buy (" + desired_product[0]["uom_name"] + " - " + desired_product[0]["uom_desc"] + "):"

            # Indicate that record retrieval has been successfully executed:
            success = True

        # Go to the "View Product" web page to continue with product-purchase attempt:
        return render_template("view_product.html", product=desired_product, form=form, success=success,
                               error_msg=error_msg,
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)

    except:  # An error has occurred.
        # Log error into system log:
        update_system_log("route: '/view_product'", traceback.format_exc())

        # Go to the "View Product" page and display error details to the user:
        return render_template("view_product.html", error_msg=f"{traceback.format_exc()}",
                               active_product_categories=active_product_categories,
                               active_prod_cat_count=active_prod_cat_count, cart_detail_count=cart_detail_count, admin=admin)


# DEFINE FUNCTIONS TO BE USED FOR THIS APPLICATION (LISTED IN ALPHABETICAL ORDER BY FUNCTION NAME):
# *************************************************************************************************
def config_database():
    """Function for configuring the database tables supporting this website"""
    global db, app, CartDetails, OrderDetails, Orders, ProductCategories, Products, UnitsOfMeasure, Users

    try:
        # Create the database object using the SQLAlchemy constructor:
        db = SQLAlchemy(model_class=Base)

        # Initialize the app with the extension:
        db.init_app(app)

        # Configure database tables (listed in alphabetical order; class names are sufficiently descriptive):
        class CartDetails(db.Model):
            __tablename__ = "cart_details"
            cart_detail_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            user_id = mapped_column(ForeignKey("users.id"), nullable=False)  # Child of 'users' table.
            user = relationship("Users", back_populates="cart_details")  # Child of "users" table.
            product_id = mapped_column(ForeignKey("products.product_id"), nullable=False)  # Child of 'products' table.
            product = relationship("Products", back_populates="cart_details")  # Child of "products" table.
            qty_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
            uom_id = mapped_column(ForeignKey("units_of_measure.uom_id"), nullable=False)  # Child of 'units_of_measure' table.
            uom = relationship("UnitsOfMeasure", back_populates="cart_details")  # Child of "units_of_measure" table.
            unit_price: Mapped[float] = mapped_column(Float, nullable=False)
            sales_amt: Mapped[float] = mapped_column(Float, nullable=False)
            unit_price_updated: Mapped[bool] = mapped_column(Boolean, nullable=False)

        class OrderDetails(db.Model):
            __tablename__ = "order_details"
            order_detail_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            order_id = mapped_column(ForeignKey("orders.order_id"), nullable=False)  # Child of 'orders' table.
            order = relationship("Orders", back_populates="order_details")  # Child of "orders" table.
            product_id = mapped_column(ForeignKey("products.product_id"), nullable=False)  # Child of 'products' table.
            product = relationship("Products", back_populates="order_details")  # Child of "products" table.
            qty_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
            uom_id = mapped_column(ForeignKey("units_of_measure.uom_id"), nullable=False)  # Child of 'units_of_measure' table.
            uom = relationship("UnitsOfMeasure", back_populates="order_details")  # Child of "units_of_measure" table.
            unit_price: Mapped[float] = mapped_column(Float, nullable=False)
            sales_amt: Mapped[float] = mapped_column(Float, nullable=False)

        class Orders(db.Model):
            __tablename__ = "orders"
            order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            date_ordered: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
            date_paid: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
            date_shipped: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
            order_details = relationship("OrderDetails", back_populates="order")  # Parent to "order_details" table.
            user_id = mapped_column(ForeignKey("users.id"), nullable=False)  # Child of 'users' table.
            user = relationship("Users", back_populates="orders")  # Child of "users" table.
            sales_amt: Mapped[float] = mapped_column(Float, nullable=False)
            tax_amt: Mapped[float] = mapped_column(Float, nullable=False)
            ship_amt: Mapped[float] = mapped_column(Float, nullable=False)
            total_amt: Mapped[float] = mapped_column(Float, nullable=False)
            notes: Mapped[str] = mapped_column(String(1000), nullable=True)

        class ProductCategories(db.Model):
            __tablename__ = "product_categories"
            category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(30), nullable=False)
            description: Mapped[str] = mapped_column(String(1000), nullable=False)
            active: Mapped[bool] = mapped_column(Boolean, nullable=False)
            products = relationship("Products", back_populates="category")  # Parent to "products" table.

        class Products(db.Model):
            __tablename__ = "products"
            product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
            category_id = mapped_column(ForeignKey("product_categories.category_id"), nullable=False)  # Child of 'product_categories' table.
            category = relationship("ProductCategories", back_populates="products")  # Child of "product_categories" table.
            unit_price_regular: Mapped[float] = mapped_column(Float, nullable=False)
            unit_price_discounted: Mapped[float] = mapped_column(Float, nullable=True)
            qty_in_stock: Mapped[int] = mapped_column(Integer, nullable=False)
            uom_id = mapped_column(ForeignKey("units_of_measure.uom_id"), nullable=False)  # Child of 'units_of_measure' table.
            uom = relationship("UnitsOfMeasure", back_populates="products")  # Child of "units_of_measure" table.
            description: Mapped[str] = mapped_column(String(1000), nullable=False)
            active: Mapped[bool] = mapped_column(Boolean, nullable=False)
            order_details = relationship("OrderDetails", back_populates="product")  # Parent to "order_details" table.
            cart_details = relationship("CartDetails", back_populates="product")  # Parent to "cart_details" table.
            product_image: Mapped[str] = mapped_column(String(1000), nullable=False)

        class UnitsOfMeasure(UserMixin, db.Model):
            __tablename__ = "units_of_measure"
            uom_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
            description: Mapped[str] = mapped_column(String(50), nullable=False)
            products = relationship("Products", back_populates="uom")  # Parent to "products" table.
            order_details = relationship("OrderDetails", back_populates="uom")  # Parent to "order_details" table.
            cart_details = relationship("CartDetails", back_populates="uom")  # Parent to "cart_details" table.

        class Users(UserMixin, db.Model):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(100), nullable=False)
            username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
            password: Mapped[str] = mapped_column(String(100), nullable=False)
            orders = relationship("Orders", back_populates="user")  # Parent to "orders" table.
            active: Mapped[bool] = mapped_column(Boolean, nullable=False)
            cart_details = relationship("CartDetails", back_populates="user")  # Parent to "cart_details" table.

        # Configure the database per the above.  If needed tables do not already exist in the DB, create them:
        with app.app_context():
            db.create_all()

        # At this point, function is presumed to have executed successfully.  Return
        # successful-execution indication to the calling function:
        return True

    except:  # An error has occurred.
        update_system_log("config_database", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return False


def config_web_forms():
    """Function for configuring the web forms supporting this website"""
    global AddOrEditProductCategoryForm, AddOrEditProductForm, AddOrEditUOMForm, AddOrEditUserForm, AddProductToCartForm, ContactForm, EditCartDetailForm, EditOrderForm, LoginForm, RegisterForm

    try:
        # CONFIGURE WEB FORMS (LISTED IN ALPHABETICAL ORDER):
        # Configure "AddOrEditProductCategory" form:
        class AddOrEditProductCategoryForm(FlaskForm):
            txt_name = StringField(label="Name:", validators=[InputRequired(), Length(max=30)])
            txt_description = TextAreaField(label="Description:", validators=[InputRequired(), Length(max=1000)])
            chk_active = BooleanField(label="Active?")
            button_submit = SubmitField(label="Save Product Category")

        # Configure "AddOrEditProduct" form:
        class AddOrEditProductForm(FlaskForm):
            txt_name = StringField(label="Name:", validators=[InputRequired(), Length(max=100)])
            lst_prod_cat = SelectField(label="Product Category:", validators=[InputRequired()])
            txt_description = TextAreaField(label="Description:", validators=[InputRequired(), Length(max=1000)])
            txt_qty_in_stock = IntegerField(label="Quantity in Stock:", validators=[InputRequired(), NumberRange(min=0, max=999999, message='Value must be a number between 0 and 999999')])
            lst_uom = SelectField(label="Unit of Measure (UOM):", validators=[InputRequired()])
            txt_unit_price_regular = DecimalField(label="Unit Price (regular):", validators=[InputRequired(), NumberRange(min=0, max=999999, message='Value must be a number between 0 and 999999')], places=2)
            txt_unit_price_discounted = DecimalField(label="Unit Price (discounted):",validators=[Optional(), NumberRange(min=0, max=999999, message='Value must be a number between 0 and 999999')], places=2)
            txt_product_image = StringField(label="Product Image (select new image file below):",render_kw={'readonly': True})
            fil_product_image = FileField(label="", validators=[Optional(), FileAllowed(['gif', 'jpeg', 'jpg', 'png'], 'Please select an image file.')])
            chk_active = BooleanField(label="Active?")
            button_submit = SubmitField(label="Save Product")

        # Configure "AddOrEditUOM" form:
        class AddOrEditUOMForm(FlaskForm):
            txt_code = StringField(label="UOM Code:", validators=[InputRequired(), Length(max=10)])
            txt_description = StringField(label="Description:", validators=[InputRequired(), Length(max=50)])
            button_submit = SubmitField(label="Save UOM")

        # Configure "AddOrEditUser" form:
        class AddOrEditUserForm(FlaskForm):
            txt_name = StringField(label="Full Name:", validators=[InputRequired(), Length(max=100)])
            txt_username = EmailField(label="E-mail Address:", validators=[InputRequired(), Email(), Length(max=100)])
            txt_password = PasswordField(label="Password:", validators=[InputRequired(), Length(max=100)])
            chk_active = BooleanField(label="Active?")
            button_submit = SubmitField(label="Save User")

        # Configure "AddProductToCart" form:
        class AddProductToCartForm(FlaskForm):
            txt_qty_ordered = IntegerField(label="Qty. to Buy:", validators=[InputRequired(), NumberRange(min=0, max=999999, message='Value must be a number between 0 and 999999')])
            button_submit = SubmitField(label="Add to Cart")

        # Configure 'contact us' form:
        class ContactForm(FlaskForm):
            txt_name = StringField(label="Your Name:", validators=[InputRequired(), Length(max=50)])
            txt_email = EmailField(label="Your E-mail Address:", validators=[InputRequired(), Email()])
            txt_message = TextAreaField(label="Your Message:", validators=[InputRequired()])
            button_submit = SubmitField(label="Send Message")

        # Configure "EditCartDetail" form:
        class EditCartDetailForm(FlaskForm):
            txt_prod_name = StringField(label="Product Ordered:",render_kw={'readonly': True})
            txt_qty_ordered = IntegerField(label="Quantity Ordered:", validators=[InputRequired(), NumberRange(min=1, max=999999, message='Value must be a number between 1 and 999999')])
            lst_uom_name = StringField(label="UOM:",render_kw={'readonly': True})
            txt_unit_price = DecimalField(label="Unit Price:", places=2, render_kw={'readonly': True})
            button_submit = SubmitField(label="Save Detail")

        # Configure "EditOrder" form:
        class EditOrderForm(FlaskForm):
            txt_order_id = IntegerField(label="Order ID:",render_kw={'readonly': True})
            txt_date_ordered = DateField(label="Date Ordered:", format='%Y-%m-%d', render_kw={'readonly': True})
            txt_date_paid = DateField(label="Date Paid:", format='%Y-%m-%d', validators=[Optional()])
            txt_date_shipped = DateField(label="Date Shipped:", format='%Y-%m-%d', validators=[Optional()])
            txt_user_name = StringField(label="Ordered By:",render_kw={'readonly': True})
            txt_user_username = StringField(label="Username:",render_kw={'readonly': True})
            txt_notes = TextAreaField(label="Notes:", validators=[Length(max=1000)])
            button_submit = SubmitField(label="Save Order")

        # Configure "Login" form (to log in existing users):
        class LoginForm(FlaskForm):
            txt_username = EmailField(label='Username (E-mail address):', validators=[InputRequired(), Email()])
            txt_password = PasswordField(label='Password:', validators=[InputRequired()])
            button_submit = SubmitField(label="Login")

        # Configure "Register" form (to register new users):
        class RegisterForm(FlaskForm):
            txt_name = StringField(label="Your Name:", validators=[InputRequired(), Length(max=100)])
            txt_username = EmailField(label='Username (E-mail address):', validators=[InputRequired(), Email(), Length(max=100)])
            txt_password = PasswordField(label='Password:', validators=[InputRequired(),Length(max=30), validators.EqualTo("txt_password_confirm","Passwords must match.")])
            txt_password_confirm = PasswordField(label='Confirm Password:', validators=[InputRequired()])
            button_submit = SubmitField(label="Register Me!")

        # At this point, function is presumed to have executed successfully.  Return
        # successful-execution indication to the calling function:
        return True

    except:  # An error has occurred.
        update_system_log("config_web_forms", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return False


def email_from_contact_page(form):
    """Function to process a message that user wishes to e-mail from this website to the website administrator."""
    try:
        # E-mail the message using the contents of the "Contact Us" web page form as input:
        with smtplib.SMTP(SENDER_HOST, port=SENDER_PORT) as connection:
            try:
                # Make connection secure, including encrypting e-mail.
                connection.starttls()
            except:
                # Return failed-execution message to the calling function:
                return "Error: Could not make connection to send e-mails. Your message was not sent."
            try:
                # Login to sender's e-mail server.
                connection.login(SENDER_EMAIL_GMAIL, SENDER_PASSWORD_GMAIL)
            except:
                # Return failed-execution message to the calling function:
                return "Error: Could not log into e-mail server to send e-mails. Your message was not sent."
            else:
                # Send e-mail.
                connection.sendmail(
                    from_addr=SENDER_EMAIL_GMAIL,
                    to_addrs=SENDER_EMAIL_GMAIL,
                    msg=f"Subject: Dessert Central - E-mail from 'Contact Us' page\n\nName: {form.txt_name.data}\nE-mail address: {form.txt_email.data}\n\nMessage:\n{form.txt_message.data}"
                )
                # Return successful-execution message to the calling function::
                return "Your message has been successfully sent."

    except:  # An error has occurred.
        update_system_log("email_from_contact_page", traceback.format_exc())

        # Return failed-execution message to the calling function:
        return "An error has occurred. Your message was not sent."


def retrieve_from_database(trans_type, **kwargs):
    """Function to retrieve data from this application's database based on the type of transaction"""
    global app, db

    try:
        with app.app_context():
            if trans_type == "get_active_product_categories":
                # Retrieve and return all active product categories, sorted by name, from the "product_categories" database table:
                return db.session.execute(db.select(ProductCategories).where(ProductCategories.active == True).order_by(func.lower(ProductCategories.name))).scalars().all()

            elif trans_type == "get_active_products_by_category":
                # Capture optional argument:
                category_id = kwargs.get("category_id", None)

                # Retrieve and return all active products, sorted by product name, belonging to the referenced product category ID:
                query_results = Products.query.join(ProductCategories, Products.category_id == ProductCategories.category_id).join(UnitsOfMeasure, Products.uom_id == UnitsOfMeasure.uom_id).filter(and_(Products.active == True, Products.category_id == category_id)).order_by(func.lower(Products.name)).with_entities(Products.product_id, Products.name, Products.unit_price_regular, Products.unit_price_discounted, Products.qty_in_stock, Products.description, Products.product_image, UnitsOfMeasure.code).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "product_id": product.product_id,
                    "name": product.name,
                    "unit_price_regular": product.unit_price_regular,
                    "unit_price_discounted": product.unit_price_discounted,
                    "qty_in_stock": product.qty_in_stock,
                    "uom": product.code,
                    "description": product.description,
                    "product_image": product.product_image
                    } for product in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_all_product_categories":
                # Retrieve and return all existing product categories, sorted by name, from the "product_categories" database table:
                return db.session.execute(db.select(ProductCategories).order_by(func.lower(ProductCategories.name))).scalars().all()

            elif trans_type == "get_all_products":
                # Retrieve and return all existing products, sorted by product category name and product name:
                query_results = db.session.execute(db.select(Products, ProductCategories, UnitsOfMeasure).join(ProductCategories, Products.category_id == ProductCategories.category_id).join(UnitsOfMeasure, Products.uom_id == UnitsOfMeasure.uom_id).order_by(func.lower(ProductCategories.name), func.lower(Products.name))).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "product_id": product.Products.product_id,
                    "name": product.Products.name,
                    "category_id": product.Products.category_id,
                    "category_name": product.ProductCategories.name,
                    "unit_price_regular": product.Products.unit_price_regular,
                    "unit_price_discounted": product.Products.unit_price_discounted,
                    "qty_in_stock": product.Products.qty_in_stock,
                    "uom_id": product.Products.uom_id,
                    "uom_name": product.UnitsOfMeasure.code,
                    "description": product.Products.description,
                    "active": product.Products.active,
                    "product_image": product.Products.product_image
                    } for product in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_all_uoms":
                # Retrieve and return all existing units of measure, sorted by code, from the "units_of_measure" database table:
                return db.session.execute(db.select(UnitsOfMeasure).order_by(func.lower(UnitsOfMeasure.code))).scalars().all()

            elif trans_type == "get_all_users":
                # Retrieve and return all existing users, sorted by name, from the "users" database table:
                return db.session.execute(db.select(Users).order_by(func.lower(Users.name))).scalars().all()

            elif trans_type == "get_cart_detail_by_id":
                # Capture optional argument:
                cart_detail_id = kwargs.get("cart_detail_id", None)

                # Retrieve the record for the desired cart detail ID:
                query_results = db.session.execute(db.select(CartDetails, Products, UnitsOfMeasure).join(Products, CartDetails.product_id == Products.product_id).join(UnitsOfMeasure, CartDetails.uom_id == UnitsOfMeasure.uom_id).where(CartDetails.cart_detail_id == cart_detail_id)).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "cart_detail_id": cart_detail.CartDetails.cart_detail_id,
                    "product_id": cart_detail.CartDetails.product_id,
                    "product_name": cart_detail.Products.name,
                    "product_image": cart_detail.Products.product_image,
                    "qty_ordered": cart_detail.CartDetails.qty_ordered,
                    "uom_id": cart_detail.CartDetails.uom_id,
                    "uom_name": cart_detail.UnitsOfMeasure.code,
                    "unit_price": cart_detail.CartDetails.unit_price,
                    "sales_amt": cart_detail.CartDetails.sales_amt,
                    "unit_price_updated": cart_detail.CartDetails.unit_price_updated
                    } for cart_detail in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_cart_detail_by_user_id_and_prod_id":
                # Capture optional arguments:
                product_id = kwargs.get("product_id", None)
                user_id = kwargs.get("user_id", None)

                # Retrieve and return cart detail record where the desired user ID and product ID is referenced:
                return db.session.execute(db.select(CartDetails).where(and_(CartDetails.product_id == product_id, CartDetails.user_id == user_id))).scalar()

            elif trans_type == "get_cart_details_by_product_id":
                # Capture optional argument:
                product_id = kwargs.get("product_id", None)

                # Retrieve and return all cart detail records where the desired product ID is referenced:
                return db.session.execute(db.select(CartDetails).where(CartDetails.product_id == product_id)).scalars().all()

            elif trans_type == "get_cart_details_by_uom_id":
                # Capture optional argument:
                uom_id = kwargs.get("uom_id", None)

                # Retrieve and return all cart detail records where the desired UOM ID is referenced:
                return db.session.execute(db.select(CartDetails).where(CartDetails.uom_id == uom_id)).scalars().all()

            elif trans_type == "get_cart_details_by_user_id":
                # Capture optional argument:
                user_id = kwargs.get("user_id", None)

                # Retrieve and return all cart details for the desired user ID:
                return db.session.execute(db.select(CartDetails).where(CartDetails.user_id == user_id)).scalars().all()

            elif trans_type == "get_cart_details_by_user_id_with_added_details":
                # Capture optional argument:
                user_id = kwargs.get("user_id", None)

                # Retrieve and return all existing cart_details for the desired user ID, sorted by product name, from the "cart_details" database table:
                query_results = db.session.execute(db.select(CartDetails, Products, UnitsOfMeasure, Users).join(Products, CartDetails.product_id == Products.product_id).join(UnitsOfMeasure, CartDetails.uom_id == UnitsOfMeasure.uom_id).join(Users, CartDetails.user_id == Users.id).where(CartDetails.user_id == user_id).order_by(func.lower(Products.name))).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "cart_detail_id": cart_detail.CartDetails.cart_detail_id,
                    "user_id": cart_detail.CartDetails.user_id,
                    "user_name": cart_detail.Users.name,
                    "user_username": cart_detail.Users.username,
                    "product_id": cart_detail.CartDetails.product_id,
                    "product_name": cart_detail.Products.name,
                    "product_image": cart_detail.Products.product_image,
                    "qty_ordered": cart_detail.CartDetails.qty_ordered,
                    "uom_id": cart_detail.CartDetails.uom_id,
                    "uom_name": cart_detail.UnitsOfMeasure.code,
                    "uom_desc": cart_detail.UnitsOfMeasure.description,
                    "unit_price": cart_detail.CartDetails.unit_price,
                    "sales_amt": cart_detail.CartDetails.sales_amt,
                    "unit_price_updated": cart_detail.CartDetails.unit_price_updated
                    } for cart_detail in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_order_by_order_id_with_added_details":
                # Capture optional argument:
                order_id = kwargs.get("order_id", None)

                # Retrieve and return desired order:
                query_results = db.session.execute(db.select(Orders, Users).join(Users, Orders.user_id == Users.id).where(Orders.order_id == order_id)).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "order_id": order.Orders.order_id,
                    "date_ordered": order.Orders.date_ordered,
                    "date_paid": order.Orders.date_paid,
                    "date_shipped": order.Orders.date_shipped,
                    "user_id": order.Orders.user_id,
                    "user_name": order.Users.name,
                    "user_username": order.Users.username,
                    "sales_amt": order.Orders.sales_amt,
                    "tax_amt": order.Orders.tax_amt,
                    "ship_amt": order.Orders.ship_amt,
                    "total_amt": order.Orders.total_amt,
                    "notes": order.Orders.notes
                    } for order in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_order_details_by_order_id":
                # Capture optional argument:
                order_id = kwargs.get("order_id", None)

                # Retrieve all order details, sorted by product name, which belong to the desired order ID:
                query_results = db.session.execute(db.select(OrderDetails, Products, UnitsOfMeasure).join(Products, OrderDetails.product_id == Products.product_id).join(UnitsOfMeasure, OrderDetails.uom_id == UnitsOfMeasure.uom_id).where(OrderDetails.order_id == order_id).order_by(func.lower(Products.name))).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "order_detail_id": order_detail.OrderDetails.order_detail_id,
                    "product_id": order_detail.OrderDetails.product_id,
                    "product_name": order_detail.Products.name,
                    "qty_ordered": order_detail.OrderDetails.qty_ordered,
                    "uom_id": order_detail.OrderDetails.uom_id,
                    "uom_name": order_detail.UnitsOfMeasure.code,
                    "unit_price": order_detail.OrderDetails.unit_price,
                    "sales_amt": order_detail.OrderDetails.sales_amt
                    } for order_detail in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_order_details_by_product_id":
                # Capture optional argument:
                product_id = kwargs.get("product_id", None)

                # Retrieve and return all order detail records where the desired product ID is referenced:
                return db.session.execute(db.select(OrderDetails).where(OrderDetails.product_id == product_id)).scalars().all()

            elif trans_type == "get_order_details_by_uom_id":
                # Capture optional argument:
                uom_id = kwargs.get("uom_id", None)

                # Retrieve and return all order detail records where the desired UOM ID is referenced:
                return db.session.execute(db.select(OrderDetails).where(OrderDetails.uom_id == uom_id)).scalars().all()

            elif trans_type == "get_orders_by_user_id":
                # Capture optional argument:
                user_id = kwargs.get("user_id", None)

                # Retrieve and return all orders for the desired user ID:
                return db.session.execute(db.select(Orders).where(Orders.user_id == user_id)).scalars().all()

            elif trans_type == "get_orders_by_user_id_with_added_details":
                # Capture optional argument:
                user_id = kwargs.get("user_id", None)

                # Retrieve and return all existing orders, sorted by order date (descending order) and order ID (ascending order).
                # - If non-admin user is logged in, only that user's orders should be retrieved.
                # - If admin is logged in, orders for ALL users should be retrieved.:
                if admin:
                    query_results = db.session.execute(db.select(Orders, Users).join(Users, Orders.user_id == Users.id).order_by(Orders.date_ordered.desc(), Orders.order_id)).all()
                else:
                    query_results = db.session.execute(db.select(Orders, Users).join(Users, Orders.user_id == Users.id).where(Orders.user_id == user_id).order_by(Orders.date_ordered.desc(), Orders.order_id)).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "order_id": order.Orders.order_id,
                    "date_ordered": order.Orders.date_ordered,
                    "date_paid": order.Orders.date_paid,
                    "date_shipped": order.Orders.date_shipped,
                    "user_id": order.Orders.user_id,
                    "user_name": order.Users.name,
                    "user_username": order.Users.username,
                    "sales_amt": order.Orders.sales_amt,
                    "tax_amt": order.Orders.tax_amt,
                    "ship_amt": order.Orders.ship_amt,
                    "total_amt": order.Orders.total_amt,
                    "notes": order.Orders.notes
                    } for order in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_prod_by_id":
                # Capture optional argument:
                product_id = kwargs.get("product_id", None)

                # Retrieve and return the record for the desired product ID:
                return db.session.execute(db.select(Products).where(Products.product_id == product_id)).scalar()

            elif trans_type == "get_prod_by_id_with_uom":
                # Capture optional argument:
                product_id = kwargs.get("product_id", None)

                # Retrieve and return desired product record, along with UOM code:
                query_results = db.session.execute(db.select(Products, UnitsOfMeasure).join(UnitsOfMeasure, Products.uom_id == UnitsOfMeasure.uom_id).where(Products.product_id == product_id)).all()

                # Specify what fields to return to the calling function for each record retrieved:
                records_to_return = [{
                    "product_id": product.Products.product_id,
                    "name": product.Products.name,
                    "unit_price_regular": product.Products.unit_price_regular,
                    "unit_price_discounted": product.Products.unit_price_discounted,
                    "qty_in_stock": product.Products.qty_in_stock,
                    "uom_id": product.Products.uom_id,
                    "uom_name": product.UnitsOfMeasure.code,
                    "uom_desc": product.UnitsOfMeasure.description,
                    "description": product.Products.description,
                    "product_image": product.Products.product_image
                    }  for product in query_results]

                # Return the retrieved records (with identified fields) to the calling function:
                return records_to_return

            elif trans_type == "get_prod_by_name":
                # Capture optional argument:
                name = kwargs.get("name", None)

                # Retrieve and return the record for the desired product name:
                return db.session.execute(db.select(Products).where(Products.name.ilike(name))).scalar()

            elif trans_type == "get_prod_by_prod_cat_id":
                # Capture optional argument:
                prod_cat_id = kwargs.get("prod_cat_id", None)

                # Retrieve and return all products belonging to the desired product category ID:
                return db.session.execute(db.select(ProductCategories).join(Products, ProductCategories.category_id == Products.category_id).where(ProductCategories.category_id == prod_cat_id)).scalars().all()

            elif trans_type == "get_prod_cat_by_id":
                # Capture optional argument:
                prod_cat_id = kwargs.get("prod_cat_id", None)

                # Retrieve and return the record for the desired product category ID:
                return db.session.execute(db.select(ProductCategories).where(ProductCategories.category_id == prod_cat_id)).scalar()

            elif trans_type == "get_prod_cat_by_name":
                # Capture optional argument:
                prod_cat_name = kwargs.get("prod_cat_name", None)

                # Retrieve and return the record for the desired product category name:
                return db.session.execute(db.select(ProductCategories).where(ProductCategories.name.ilike(prod_cat_name))).scalar()

            elif trans_type == "get_products_by_uom_id":
                # Capture optional argument:
                uom_id = kwargs.get("uom_id", None)

                # Retrieve and return all product records where the desired UOM ID is referenced:
                return db.session.execute(db.select(Products).where(Products.uom_id == uom_id)).scalars().all()

            elif trans_type == "get_uom_by_code":
                # Capture optional argument:
                code = kwargs.get("code", None)

                # Retrieve and return the record for the desired unit-of-measure code:
                return db.session.execute(db.select(UnitsOfMeasure).where(UnitsOfMeasure.code.ilike(code))).scalar()

            elif trans_type == "get_uom_by_id":
                # Capture optional argument:
                uom_id = kwargs.get("uom_id", None)

                # Retrieve and return the record for the desired unit-of-measure ID:
                return db.session.execute(db.select(UnitsOfMeasure).where(UnitsOfMeasure.uom_id == uom_id)).scalar()

            elif trans_type == "get_user_by_id":
                # Capture optional argument:
                user_id = kwargs.get("user_id", None)

                # Retrieve and return the record for the desired user ID:
                return db.session.execute(db.select(Users).where(Users.id == user_id)).scalar()

            elif trans_type == "get_user_by_username":
                # Capture optional argument:
                username = kwargs.get("username", None)

                # Retrieve and return the record for the desired username:
                return db.session.execute(db.select(Users).where(Users.username.ilike(username))).scalar()

    except:  # An error has occurred.
        update_system_log("retrieve_from_database (" + trans_type + ")", traceback.format_exc())

        # Return empty dictionary as a failed-execution indication to the calling function:
        return {}


def run_app():
    """Main function for this application"""
    global app, admin

    try:
        # Set base directory for this application:
        basedir = os.path.abspath(os.path.dirname(__file__))

        # Configure the SQLite database, relative to the app instance folder:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shop.db"

        # Configure location where product images will be stored:
        app.config["PRODUCT_IMAGES"] = os.path.join(basedir,"static/product_images")

        # Initialize an instance of Bootstrap5, using the "app" object defined above as a parameter:
        Bootstrap5(app)

        # Retrieve the secret key to be used for CSRF protection:
        app.secret_key = SECRET_KEY_FOR_CSRF_PROTECTION

        # Configure database tables.  If function failed, update system log and return
        # failed-execution indication to the calling function:
        if not config_database():
            update_system_log("run_app", "Error: Database configuration failed.")
            return False

        # Configure web forms.  If function failed, update system log and return
        # failed-execution indication to the calling function:
        if not config_web_forms():
            update_system_log("run_app", "Error: Web forms configuration failed.")
            return False

    except:  # An error has occurred.
        update_system_log("run_app", traceback.format_exc())
        return False


def get_active_product_categories():
    """Function to retrieve all active product categories"""
    try:
        # Initialize variable to capture number of active product categories retrieved from the database:
        active_prod_cat_count = 0

        # Get information on active product categories in the database:
        active_product_categories = retrieve_from_database("get_active_product_categories")
        if not(active_product_categories == {} or active_product_categories == []):
            active_prod_cat_count = len(active_product_categories)  # Record count of active product categories retrieved from the database.

        # Return results to the calling function:
        return active_product_categories, active_prod_cat_count

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("get_active_product_categories", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return {},0


def get_active_products_by_category(category_id):
    """Function to retrieve all active products for a particular product category"""
    try:
        # Initialize variable to capture number of active products retrieved from the database:
        active_prod_count = 0

        # Get information on active products in the database for the referenced product category:
        active_products = retrieve_from_database("get_active_products_by_category", category_id=category_id)
        if not(active_products == {} or active_products == []):
            active_prod_count = len(active_products)  # Record count of active products retrieved from the database for the reference product category.

        # Return results to the calling function:
        return active_products, active_prod_count

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("get_active_products_by_category", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return {},0


def get_cart_detail_count():
    """Function to retrieve count of cart detail records in cart for user currently logged in"""
    try:
        # Initialize variable to capture number of cart details retrieved from the database:
        cart_detail_count = 0

        # Get information on cart detail records in the database for user currently logged in.
        # If no user is logged in, return a count of zero (via "AttributeError" exception handler below):
        cart_details = retrieve_from_database("get_cart_details_by_user_id", user_id=current_user.id)
        if not(cart_details == {} or cart_details == []):
            cart_detail_count = len(cart_details)  # Record count of cart details in cart.

        # Return result to the calling function:
        return cart_detail_count

    except AttributeError:
        return 0

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("get_cart_detail_count", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return "ERROR"


def get_product_categories_for_selection():
    """Function to retrieve all product categories for populating selection fields on input form(s)"""
    try:
        # Initialize variable to capture number of product categories retrieved from the database:
        prod_cat_count = 0

        # Get information on product categories in the database:
        prod_cats = retrieve_from_database("get_all_product_categories")
        if not(prod_cats == {} or prod_cats == []):
            prod_cat_count = len(prod_cats)  # Record count of units of measure retrieved from the database.

        # Return results to the calling function:
        return prod_cats, prod_cat_count

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("get_product_categories_for_selection", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return {},0


def get_uoms_for_selection():
    """Function to retrieve all units of measure for populating selection fields on input form(s)"""
    try:
        # Initialize variable to capture number of units of measure retrieved from the database:
        uom_count = 0

        # Get information on units of measure in the database:
        uoms = retrieve_from_database("get_all_uoms")
        if not(uoms == {} or uoms == []):
            uom_count = len(uoms)  # Record count of units of measure retrieved from the database.

        # Return results to the calling function:
        return uoms, uom_count

    except:  # An error has occurred.
        # Log error into system log file:
        update_system_log("get_uoms_for_selection", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return {},0


def update_database(trans_type, **kwargs):
    """Function to update this application's database based on the type of transaction"""
    try:
        with app.app_context():
            if trans_type == "add_prod":
                # Capture optional argument:
                form = kwargs.get("form", None)

                # Upload selected image file to this application's designated directory for product images:
                product_image_file = form.fil_product_image.data
                file_path = os.path.join(app.config['PRODUCT_IMAGES'], product_image_file.filename)
                product_image_file.save(file_path)

                # Upload, to the "products" database table, contents of the "form" parameter passed to this function:
                new_records = []

                new_record = Products(
                    name=form.txt_name.data,
                    category_id=int(form.lst_prod_cat.data),
                    description=form.txt_description.data,
                    qty_in_stock=form.txt_qty_in_stock.data,
                    uom_id=int(form.lst_uom.data),
                    unit_price_regular=form.txt_unit_price_regular.data,
                    unit_price_discounted=form.txt_unit_price_discounted.data,
                    product_image=form.fil_product_image.data.filename,
                    active=form.chk_active.data
                )
                new_records.append(new_record)

                db.session.add_all(new_records)
                db.session.commit()

            elif trans_type == "add_prod_cat":
                # Capture optional argument:
                form = kwargs.get("form", None)

                # Upload, to the "product_categories" database table, contents of the "form" parameter passed to this function:
                new_records = []

                new_record = ProductCategories(
                    name=form.txt_name.data,
                    description=form.txt_description.data,
                    active=form.chk_active.data
                )
                new_records.append(new_record)

                db.session.add_all(new_records)
                db.session.commit()

            elif trans_type == "add_prod_to_cart":
                # Capture optional arguments:
                form = kwargs.get("form", None)
                product = kwargs.get("product", None)
                user_id = kwargs.get("user_id", None)

                # Determine whether the desired product is regular or discounted:
                if product["unit_price_discounted"] == None:
                    unit_price = product["unit_price_regular"]
                else:
                    unit_price = product["unit_price_discounted"]

                # Upload, to the "cart_details" database table, contents of the "form" parameter passed to this function:
                new_records = []

                new_record = CartDetails(
                    user_id=int(user_id),
                    product_id=int(product["product_id"]),
                    qty_ordered=form.txt_qty_ordered.data,
                    uom_id=int(product["uom_id"]),
                    unit_price=unit_price,
                    sales_amt=form.txt_qty_ordered.data * unit_price,
                    unit_price_updated=False
                )
                new_records.append(new_record)

                db.session.add_all(new_records)
                db.session.commit()

            elif trans_type == "add_uom":
                # Capture optional argument:
                form = kwargs.get("form", None)

                # Upload, to the "units_of_measure" database table, contents of the "form" parameter passed to this function:
                new_records = []

                new_record = UnitsOfMeasure(
                    code=form.txt_code.data,
                    description=form.txt_description.data,
                )
                new_records.append(new_record)

                db.session.add_all(new_records)
                db.session.commit()

            elif trans_type == "add_user":
                # Capture optional argument:
                form = kwargs.get("form", None)

                # Upload, to the "users" database table, contents of the "form" parameter passed to this function:
                new_records = []

                new_record = Users(
                    name=form.txt_name.data,
                    username=form.txt_username.data,
                    password=generate_password_hash(form.txt_password.data, method='pbkdf2:sha256', salt_length=8),
                    active=form.chk_active.data
                )
                new_records.append(new_record)

                db.session.add_all(new_records)
                db.session.commit()

            elif trans_type == "add_user_via_registration":
                # Capture optional argument:
                form = kwargs.get("form", None)

                # Upload, to the "users" database table, contents of the "form" parameter passed to this function.
                # Set user status to active since this involves a new user registration:
                new_records = []

                new_record = Users(
                    name=form.txt_name.data,
                    username=form.txt_username.data,
                    password=generate_password_hash(form.txt_password.data, method='pbkdf2:sha256', salt_length=8),
                    active=1
                )
                new_records.append(new_record)

                db.session.add_all(new_records)
                db.session.commit()

            elif trans_type == "delete_cart_detail_by_id":
                # Capture optional argument:
                cart_detail_id = kwargs.get("cart_detail_id", None)

                # Delete the cart detail record associated with the selected ID:
                db.session.query(CartDetails).where(CartDetails.cart_detail_id == cart_detail_id).delete()
                db.session.commit()

            elif trans_type == "delete_prod_by_id":
                # Capture optional argument:
                product_id = kwargs.get("product_id", None)

                # Delete the product record associated with the selected ID:
                db.session.query(Products).where(Products.product_id == product_id).delete()
                db.session.commit()

            elif trans_type == "delete_prod_cat_by_id":
                # Capture optional argument:
                prod_cat_id = kwargs.get("prod_cat_id", None)

                # Delete the product category record associated with the selected ID:
                db.session.query(ProductCategories).where(ProductCategories.category_id == prod_cat_id).delete()
                db.session.commit()

            elif trans_type == "delete_uom_by_id":
                # Capture optional argument:
                uom_id = kwargs.get("uom_id", None)

                # Delete the unit-of-measure record associated with the selected ID:
                db.session.query(UnitsOfMeasure).where(UnitsOfMeasure.uom_id == uom_id).delete()
                db.session.commit()

            elif trans_type == "delete_user_by_id":
                # Capture optional argument:
                user_id = kwargs.get("user_id", None)

                # Delete the user record associated with the selected ID:
                db.session.query(Users).filter(Users.id == user_id).delete()
                db.session.commit()

            elif trans_type == "edit_order":
                # Capture optional argument:
                form = kwargs.get("form", None)
                order_id = kwargs.get("order_id", None)

                # Edit order record for the selected ID, using editable data in the "form" parameter passed to this function:
                record_to_edit = db.session.query(Orders).filter(Orders.order_id == order_id).first()
                if form.txt_date_paid.data == None:
                    record_to_edit.date_paid = None
                else:
                    record_to_edit.date_paid = datetime(form.txt_date_paid.data.year, form.txt_date_paid.data.month, form.txt_date_paid.data.day)
                if form.txt_date_shipped.data == None:
                    record_to_edit.date_shipped = None
                else:
                    record_to_edit.date_shipped = datetime(form.txt_date_shipped.data.year, form.txt_date_shipped.data.month, form.txt_date_shipped.data.day)
                record_to_edit.notes = form.txt_notes.data

                db.session.commit()

            elif trans_type == "edit_prod_cat":
                # Capture optional arguments:
                form = kwargs.get("form", None)
                prod_cat_id = kwargs.get("prod_cat_id", None)

                # Edit product category record for the selected ID, using data in the "form" parameter passed to this function:
                record_to_edit = db.session.query(ProductCategories).filter(ProductCategories.category_id == prod_cat_id).first()
                record_to_edit.name = form.txt_name.data
                record_to_edit.description = form.txt_description.data
                record_to_edit.active = form.chk_active.data

                db.session.commit()

            elif trans_type == "edit_prod_in_cart":
                # Capture optional arguments:
                cart_detail_id = kwargs.get("cart_detail_id", None)
                qty_updated = kwargs.get("qty_updated", None)

                # Edit cart detail record for the selected ID, using updated order quantity passed to this function:
                record_to_edit = db.session.query(CartDetails).filter(CartDetails.cart_detail_id == cart_detail_id).first()
                record_to_edit.qty_ordered = qty_updated
                record_to_edit.sales_amt = qty_updated * record_to_edit.unit_price

                db.session.commit()

            elif trans_type == "edit_uom":
                # Capture optional arguments:
                form = kwargs.get("form", None)
                uom_id = kwargs.get("uom_id", None)

                # Edit unit-of-measure record for the selected ID, using data in the "form" parameter passed to this function:
                record_to_edit = db.session.query(UnitsOfMeasure).filter(UnitsOfMeasure.uom_id == uom_id).first()
                record_to_edit.code = form.txt_code.data
                record_to_edit.description = form.txt_description.data

                db.session.commit()

            elif trans_type == "edit_user":
                # Capture optional arguments:
                form = kwargs.get("form", None)
                user_id = kwargs.get("user_id", None)

                # Edit user record for the selected ID, using data in the "form" parameter passed to this function:
                record_to_edit = db.session.query(Users).filter(Users.id == user_id).first()
                record_to_edit.name = form.txt_name.data
                record_to_edit.username = form.txt_username.data
                record_to_edit.password = generate_password_hash(form.txt_password.data, method='pbkdf2:sha256', salt_length=8)
                record_to_edit.active = form.chk_active.data

                db.session.commit()

        # Return successful-execution indication to the calling function:
        return True

    except:  # An error has occurred.
        update_system_log("update_database (" + trans_type + ")", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return False


def update_database_with_trans(trans_type, **kwargs):
    """Function to perform a multi-step database update (wrapped inside a database transaction) based on the type of transaction"""
    try:
        if trans_type == "create_order":
            # Capture optional argument:
            user_id = kwargs.get("user_id", None)

            # Initialize a "savepoint" object which will allow nesting of multiple db update steps within one transaction so that
            # either all steps execute successfully and are committed OR are all rolled back:
            savepoint = db.session.begin_nested()

            # Retrieve order record with the highest order ID number:
            existing_orders = db.session.query(Orders).order_by(Orders.order_id.desc()).first()
            if existing_orders == None:
                new_order_id = 1
            else:  # No orders were retrieved:
                new_order_id = existing_orders.order_id + 1

            # Retrieve existing cart details:
            existing_cart_details = retrieve_from_database("get_cart_details_by_user_id_with_added_details", user_id=user_id)
            if existing_cart_details == {} or existing_cart_details == []:
                savepoint.rollback()
                return False

            else:
                # Initialize variables for total sales, tax, shipping, and grand total values across cart details:
                sum_sales_amt = 0
                sum_tax_amt = 0
                sum_ship_amt = 0
                sum_total_amt = 0

                # Total the sales_amt values across cart details:
                for detail in existing_cart_details:
                    sum_sales_amt += detail["sales_amt"]

                # Calculate the totaL tax and shipping amounts applicable to the cart contents:
                sum_tax_amt = round(sum_sales_amt * RATE_SALES_TAX, 2)
                sum_ship_amt = round(sum_sales_amt * RATE_SHIPPING, 2)

                # Calculate the grand total amt applicable to the cart contents:
                sum_total_amt = sum_sales_amt + sum_tax_amt + sum_ship_amt

                # Create a new order for this purchase:
                new_records = []
                new_record = Orders(
                    order_id=new_order_id,
                    date_ordered=datetime.date(datetime.now()),
                    date_paid=datetime.date(datetime.now()),
                    user_id=user_id,
                    sales_amt=sum_sales_amt,
                    tax_amt=sum_tax_amt,
                    ship_amt=sum_ship_amt,
                    total_amt=sum_total_amt
                )
                new_records.append(new_record)
                db.session.add_all(new_records)

                # Upload, to the "order_details" database table, existing cart details:
                new_records = []
                for detail in existing_cart_details:
                    new_record = OrderDetails(
                        order_id=new_order_id,
                        product_id=int(detail["product_id"]),
                        qty_ordered=detail["qty_ordered"],
                        uom_id=int(detail["uom_id"]),
                        unit_price=detail["unit_price"],
                        sales_amt=detail["sales_amt"],
                    )
                    new_records.append(new_record)
                    db.session.add_all(new_records)

                # Update quantity in stock for each product involved in this order:
                for detail in existing_cart_details:
                    ordered_product = retrieve_from_database("get_prod_by_id", product_id=detail["product_id"])
                    if ordered_product == {} or ordered_product == None:
                        return False
                    else:
                        record_to_edit = db.session.query(Products).filter(Products.product_id == detail["product_id"]).first()
                        if record_to_edit == None:
                            return False
                        else:
                            record_to_edit.qty_in_stock -= detail["qty_ordered"]

            # Delete cart contents:
            db.session.query(CartDetails).where(CartDetails.user_id == user_id).delete()

            # Commit the multi-step database transaction:
            savepoint.commit()

            # Return new order ID to the calling function:
            return new_order_id

        elif trans_type == "edit_product":
            # Initialize a "savepoint" object which will allow nesting of multiple db update steps within one transaction so that
            # either all steps execute successfully and are committed OR are all rolled back:
            savepoint = db.session.begin_nested()

            # Capture optional arguments:
            form = kwargs.get("form", None)
            product_id = kwargs.get("product_id", None)

            # Perform part 1 of multi-step database transaction (edit product record):
            # Initialize variable to flag whether product image is being changed:
            edit_product_image = False

            # If new product image is being supplied, then include as part of record editing:
            if form.fil_product_image.data != None:
                # Indicate that new product image is being supplied.
                edit_product_image = True

                # Upload selected image file to this application's designated directory for product images:
                uploaded_file = form.fil_product_image.data
                file_path = os.path.join(app.config['PRODUCT_IMAGES'], uploaded_file.filename)
                uploaded_file.save(file_path)

            # Retrieve desired product record:
            record_to_edit = db.session.query(Products).filter(Products.product_id == product_id).first()

            if record_to_edit != None:
                # Capture the price in effect prior to database update:
                if record_to_edit.unit_price_discounted == None:
                    unit_price_before_update = record_to_edit.unit_price_regular
                else:
                    unit_price_before_update = record_to_edit.unit_price_discounted

                # Capture the price which will be in effect prior to database update:
                if form.txt_unit_price_discounted.data == None:
                    unit_price_after_update = form.txt_unit_price_regular.data
                else:
                    unit_price_after_update = form.txt_unit_price_discounted.data

                # Edit product record for the selected ID, using data in the "form" parameter passed to this function:
                record_to_edit.name = form.txt_name.data
                record_to_edit.category_id = form.lst_prod_cat.data
                record_to_edit.description = form.txt_description.data
                record_to_edit.qty_in_stock = form.txt_qty_in_stock.data
                record_to_edit.uom_id = form.lst_uom.data
                record_to_edit.unit_price_regular = form.txt_unit_price_regular.data
                record_to_edit.unit_price_discounted = form.txt_unit_price_discounted.data
                if edit_product_image:
                    record_to_edit.product_image=form.fil_product_image.data.filename
                record_to_edit.active = form.chk_active.data

            else:
                # Return failed-execution indication to the calling function:
                return False

            # If price in effect has been changed, perform part 2 of multi-step database transaction:
            # (Update price for that product in cart detail records):
            if unit_price_before_update != unit_price_after_update:
                db.session.query(CartDetails).filter(CartDetails.product_id == product_id).update(
                    {'unit_price': unit_price_after_update,
                     'sales_amt': CartDetails.qty_ordered * unit_price_after_update,
                     'unit_price_updated': True
                     })

            # Commit the multi-step database transaction:
            savepoint.commit()

        # Return successful-execution indication to the calling function:
        return True

    except:  # An error has occurred.
        # Roll back database transaction:
        savepoint.rollback()

        # Log error into system log file:
        update_system_log("update_database_with_trans (" + trans_type + ")", traceback.format_exc())

        # Return failed-execution indication to the calling function:
        return False


def update_system_log(activity, log):
    """Function to update the system log, either to log errors encountered or log successful execution of milestone admin. updates"""
    try:
        # Capture current date/time:
        current_date_time = datetime.now()
        current_date_time_file = current_date_time.strftime("%Y-%m-%d")

        # Update log file.  If log file does not exist, create it:
        with open("log_dessert_central_" + current_date_time_file + ".txt", "a") as f:
            f.write(datetime.now().strftime("%Y-%m-%d @ %I:%M %p") + ":\n")
            f.write(activity + ": " + log + "\n")

        # Close the log file:
        f.close()

    except:
        dlg = wx.App()
        dlg = wx.MessageBox(f"Error: System log could not be updated.\n{traceback.format_exc()}", 'Error',
                            wx.OK | wx.ICON_INFORMATION)


def validate_delete(entity, **kwargs):
    """Function to check if "delete" request meets database requirements prior to deleting desired record"""
    try:
        if entity == "prod_cat":
            # Capture optional argument:
            prod_cat_id = kwargs.get("prod_cat_id", None)

            # Check if prod_cat_id exists in the "products" database table.  If yes, then deletion cannot proceed:
            prod_cat_id_in_products = retrieve_from_database("get_prod_by_prod_cat_id", prod_cat_id=prod_cat_id)
            if prod_cat_id_in_products == {}:
                return False, "An error has occurred in validating deletion request."
            elif prod_cat_id_in_products != []:
                return False, "Product category exists in one or more products.  Deletion cannot be performed."

        elif entity == "product":
            # Capture optional argument:
            product_id = kwargs.get("product_id", None)

            # Check if product_id exists in the "cart_details" database table.  If yes, then deletion cannot proceed:
            product_id_in_cart_details = retrieve_from_database("get_cart_details_by_product_id", product_id=product_id)
            if product_id_in_cart_details == {}:
                return False, "An error has occurred in validating deletion request."
            elif product_id_in_cart_details != []:
                return False, "Product exists in one or more cart details.  Deletion cannot be performed."

            # Check if product_id exists in the "order_details" database table.  If yes, then deletion cannot proceed:
            product_id_in_order_details = retrieve_from_database("get_order_details_by_product_id", product_id=product_id)
            if product_id_in_order_details == {}:
                return False, "An error has occurred in validating deletion request."
            elif product_id_in_order_details != []:
                return False, "Product exists in one or more order details.  Deletion cannot be performed."

        elif entity == "user":
            # Capture optional argument:
            user_id = kwargs.get("user_id", None)

            # Check if user_id belongs to the admin.:
            if user_id == 1:
                return False, "Selected user cannot be deleted."

            # Check if user_id exists in the "orders" database table.  If yes, then deletion cannot proceed:
            user_id_in_orders = retrieve_from_database("get_orders_by_user_id", user_id=user_id)
            if user_id_in_orders == {}:
                return False, "An error has occurred in validating deletion request."
            elif user_id_in_orders != []:
                return False, "User exists in one or more orders.  Deletion cannot be performed."

            # Check if user_id exists in the "cart_details" database table.  If yes, then deletion cannot proceed:
            user_id_in_cart_details = retrieve_from_database("get_cart_details_by_user_id", user_id=user_id)
            if user_id_in_cart_details == {}:
                return False, "An error has occurred in validating deletion request."
            elif user_id_in_cart_details != []:
                return False, "User exists in one or more cart details.  Deletion cannot be performed."

        elif entity == "uom":
            # Capture optional argument:
            uom_id = int(kwargs.get("uom_id", None))

            # Check if uom_id exists in the "cart_details" database table.  If yes, then deletion cannot proceed:
            uom_id_in_cart_details = retrieve_from_database("get_cart_details_by_uom_id", uom_id=uom_id)
            if uom_id_in_cart_details == {}:
                return False, "An error has occurred in validating deletion request."
            elif uom_id_in_cart_details != []:
                return False, "UOM exists in one or more cart details.  Deletion cannot be performed."

            # Check if uom_id exists in the "order_details" database table.  If yes, then deletion cannot proceed:
            uom_id_in_order_details = retrieve_from_database("get_order_details_by_uom_id", uom_id=uom_id)
            if uom_id_in_order_details == {}:
                return False, "An error has occurred in validating deletion request."
            elif uom_id_in_order_details != []:
                return False, "UOM exists in one or more order details.  Deletion cannot be performed."

            # Check if uom_id exists in the "products" database table.  If yes, then deletion cannot proceed:
            uom_id_in_products = retrieve_from_database("get_products_by_uom_id", uom_id=uom_id)
            if uom_id_in_products == {}:
                return False, "An error has occurred in validating deletion request."
            elif uom_id_in_products != []:
                return False, "UOM exists in one or more products.  Deletion cannot be performed."

        # At this point, validation is deemed to have passed all validation checks.
        # Return successful-validation indication to the calling function:
        return True, ""

    except:  # An error has occurred:
        return False, "An error has occurred in validating deletion request."


# Run main function for this application:
run_app()

# Destroy the object that was created to show user dialog and message boxes:
dlg.Destroy()

if __name__ == "__main__":
    app.run(debug=True, port=5003)
