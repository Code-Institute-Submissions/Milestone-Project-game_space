from django.shortcuts import render, redirect, reverse, get_object_or_404, HttpResponse
from django.views.decorators.http import require_POST
from .forms import OrderForm
from django.contrib import messages
from django.conf import settings
from .models import Discount, OrderLineItem, Order
from bag.contexts import bag_contents
from games.models import Game
from profiles.models import UserProfile
from profiles.forms import UserProfileForm
import json

import stripe
# Create your views here.


@require_POST
def cache_checkout_data(request):
    discount = request.session.get('discount', {})
    bag = request.session.get('bag', {})
    try:
        pid = request.POST.get('client_secret').split('_secret')[0]
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.PaymentIntent.modify(pid, metadata={
            'username': request.user,
            'save_info': request.POST.get('save_info'),
            'bag': json.dumps(bag),
            'discount': discount
        })
        return HttpResponse(request, status=200)
    except Exception as e:
        print(e)
        messages.error(request, f'An error has occured : {e}')
        return HttpResponse(request, status=400)


def checkout(request):
    stripe_secret_key = settings.STRIPE_SECRET_KEY
    bag_info = bag_contents(request)
    if request.POST:
        bag = request.session.get("bag", {})
        form_data = {
            'full_name': request.POST['full_name'],
            'email': request.POST['email'],
            'phone_number': request.POST['phone_number'],
            'country': request.POST['country'],
            'postcode': request.POST['postcode'],
            'town_or_city': request.POST['town_or_city'],
            'street_address1': request.POST['street_address1'],
            'street_address2': request.POST['street_address2'],
            'county': request.POST['county'],
        }
        order_form = OrderForm(form_data)
        if order_form.is_valid():
            order = order_form.save(commit=False)
            pid = request.POST.get('client_secret').split('_secret')[0]
            order.stripe_pid = pid
            order.original_bag = json.dumps(bag)
            order.save()

            # Grab the payment intent from the pid using Stripe API
            # Confirm the ZIP code of that payment otherwise in the backend of Stripe it will appear incomplete

            for item in bag_info['bag_items']:
                try:
                    game = get_object_or_404(Game, pk=item['game_id'])
                    console = item['console']
                    quantity = item['quantity']
                    line_item_total = item['game'].price * quantity
                    if 'discount' in item:
                        discount = item['discount']
                        total_after_discount = item['discount_price'] * quantity
                        order_line_item = OrderLineItem(
                            order=order,
                            game=game,
                            game_console=console,
                            quantity=quantity,
                            lineitem_total=line_item_total,
                            discount=discount,
                            total_after_discount=total_after_discount
                        )
                        order_line_item.save()
                    else:
                        order_line_item = OrderLineItem(
                            order=order,
                            game=game,
                            game_console=console,
                            quantity=quantity,
                            lineitem_total=line_item_total
                        )
                        order_line_item.save()
                except Game.DoesNotExist:
                    messages.error(request, (
                        "One of the games in your bag wasn't found in our database. "
                        "Please call us for assistance!")
                    )
                    order.delete()
                    return redirect(reverse('view_bag'))
            request.session['save_info'] = 'save-info' in request.POST
            return redirect(reverse('checkout_success', args=[order.order_number]))
        else:
            messages.error(request, 'There was an error with your form. \
                Please double check your information.')

    else:
        bag = request.session.get("bag", {})
        if not bag:
            messages.error(request, "Sorry there is nothing in your bag.")
            return redirect(reverse("games"))
        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                order_form = OrderForm(initial={
                    'full_name': profile.user.get_full_name(),
                    'email': profile.user.email,
                    'phone_number': profile.default_phone_number,
                    'country': profile.default_country,
                    'postcode': profile.default_postcode,
                    'town_or_city': profile.default_town_or_city,
                    'street_address1': profile.default_street_address1,
                    'street_address2': profile.default_street_address2,
                    'county': profile.default_county,
                })
            except UserProfile.DoesNotExist:
                order_form = OrderForm()
        else:
            order_form = OrderForm()
        current_bag = bag_contents(request)
        if "discount_total" in current_bag:
            total = current_bag["discount_total"]
        else:
            total = current_bag["grand_total"]
        stripe_total = round(total*100)
        stripe.api_key = stripe_secret_key
        intent = stripe.PaymentIntent.create(
            amount=stripe_total,
            currency=settings.STRIPE_CURRENCY,
        )
        template = 'checkout/checkout.html'
        context = {
            'order_form': order_form,
            'client_secret': intent.client_secret,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY
        }
        return render(request, template, context)


def get_discount(request):
    discount_code = request.POST.get('discount-code')
    redirect_url = request.POST.get('redirect_url')
    try:
        discount = Discount.objects.get(pk=discount_code)
        if discount:
            request.session['discount'] = discount_code
            messages.success(
                request, f'Successfully applied discount code: {discount_code}')
        else:
            messages.error(
                request, f'Could not find discount_code: {discount_code}. Please check spelling and try again.')
    except Exception as e:
        print(f'Error : {e}')
        messages.error(
            request, f'Could not find discount_code: {discount_code}. Please check spelling and try again.')
    return redirect(redirect_url)


def checkout_success(request, order_number):
    """
    Handle successful checkouts
    """
    save_info = request.session.get('save_info')
    order = get_object_or_404(Order, order_number=order_number)
    messages.success(request, f'Order successfully processed! \
        Your order number is {order_number}. A confirmation \
        email will be sent to {order.email}.')
    if request.user.is_authenticated:
        profile = UserProfile.objects.get(user=request.user)
        # Attach the user's profile to the order
        order.user_profile = profile
        order.save()
    if save_info:
        profile_data = {
            'default_phone_number': order.phone_number,
            'default_email': order.email,
            'default_street_address1': order.street_address1,
            'default_street_address2': order.street_address2,
            'default_town_or_city': order.town_or_city,
            'default_county': order.county,
            'default_postcode': order.postcode,
            'default_country': order.country,
        }
        user_profile_form = UserProfileForm(profile_data, instance=profile)
        if user_profile_form.is_valid():
            user_profile_form.save()

    if 'bag' in request.session:
        del request.session['bag']
    if 'discount' in request.session:
        del request.session['discount']
    template = 'checkout/checkout_success.html'
    context = {
        'order': order,
    }

    return render(request, template, context)
