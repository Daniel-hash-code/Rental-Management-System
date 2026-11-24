from django.shortcuts import render

def home(request):
    """
    Public RentFlow homepage.
    Visitors do not need to authenticate to access this page.
    """
    return render(request, "home.html")
