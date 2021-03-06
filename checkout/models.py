from django.db import models
from django.db.models import Sum
from games.models import Game, Console
from django.conf import settings
import uuid
from django_countries.fields import CountryField
from profiles.models import UserProfile


class Discount(models.Model):
    name = models.CharField(max_length=254, null=False, blank=False)
    code = models.CharField(max_length=10, null=False,
                            blank=False, primary_key=True)
    expiry_date = models.DateField(auto_now=False)
    offer_discount = models.DecimalField(max_digits=2,
                                         decimal_places=0, null=True, blank=True)
    offer_details = models.CharField(max_length=254, null=False, blank=False)
    games_or_consoles_valid = models.JSONField()

    def __str__(self):
        return self.name


# Taken from CI Ecommerce project - edited
class Order(models.Model):
    order_number = models.CharField(max_length=32, null=False, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='orders')
    full_name = models.CharField(max_length=50, null=False, blank=False)
    email = models.EmailField(max_length=254, null=False, blank=False)
    phone_number = models.CharField(max_length=20, null=False, blank=False)
    country = CountryField(blank_label="Country *", null=False, blank=False)
    postcode = models.CharField(max_length=20, blank=False)
    town_or_city = models.CharField(max_length=40, null=False, blank=False)
    street_address1 = models.CharField(max_length=80, null=False, blank=False)
    street_address2 = models.CharField(max_length=80, blank=True, null=True)
    county = models.CharField(max_length=80, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    delivery_cost = models.DecimalField(
        max_digits=6, decimal_places=2, null=False, default=0)
    order_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=False, default=0)
    grand_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=False, default=0)
    original_total = models.DecimalField(
        max_digits=10, decimal_places=2, blank=False, null=False, default=0)
    original_bag = models.TextField(null=False, blank=False, default='')
    stripe_pid = models.CharField(
        max_length=254, null=False, blank=False, default='')

    def _generate_order_number(self):
        return uuid.uuid4().hex.upper()

    def update_total(self):
        self.order_total = 0
        # Calculates totals dependent on if there is a discount or not.
        # (Original total is the cost of orders without discount for calculating delivery costs)
        self.original_total = self.lineitems.aggregate(Sum('lineitem_total'))[
            'lineitem_total__sum'] or 0
        for item in self.lineitems.all():
            if item.discount:
                self.order_total += item.total_after_discount
            else:
                self.order_total += item.lineitem_total

        if self.order_total < settings.FREE_DELIVERY_THRESHOLD:
            self.delivery_cost = self.original_total * \
                settings.STANDARD_DELIVERY_PERCENTAGE/100
        else:
            self.delivery_cost = 0
        self.grand_total = self.delivery_cost + self.order_total
        self.save()

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number


class OrderLineItem(models.Model):
    order = models.ForeignKey(Order, null=False, blank=False,
                              on_delete=models.CASCADE, related_name='lineitems')
    game = models.ForeignKey(
        Game, null=False, blank=False, on_delete=models.CASCADE)
    game_console = models.ForeignKey(
        Console, null=False, blank=False, on_delete=models.PROTECT)
    quantity = models.IntegerField(null=False, blank=False, default=0)
    lineitem_total = models.DecimalField(
        max_digits=6, decimal_places=2, null=False, blank=False, editable=False)
    discount = models.ForeignKey(
        Discount, blank=True, null=True, on_delete=models.CASCADE)
    total_after_discount = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.lineitem_total = self.quantity * self.game.price
        if self.discount:
            self.total_after_discount = self.lineitem_total * \
                (1 - self.discount.offer_discount/100)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'SKU {self.game.sku} on order {self.order.order_number}'
