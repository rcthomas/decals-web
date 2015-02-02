from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    # url(r'^image/(\d*)/(\d*)/(\d*).jpg', 'map.views.map_image'),
    # url(r'^cosmos-grz/(\d*)/(\d*)/(\d*).jpg', 'map.views.map_cosmos_grz'),
    # url(r'^cosmos-urz/(\d*)/(\d*)/(\d*).jpg', 'map.views.map_cosmos_urz'),

    # Tiles
    url(r'^decals/(\d+)/(\d+)/(\d+)/(\d+).jpg', 'map.views.map_decals'),
    url(r'^decals-pr/(\d+)/(\d+)/(\d+)/(\d+).jpg', 'map.views.map_decals_pr'),
    url(r'^decals-model/(\d+)/(\d+)/(\d+)/(\d+).jpg', 'map.views.map_decals_model'),
    url(r'^des-stripe82/(\d+)/(\d+)/(\d+)/(\d+).jpg', 'map.views.map_des_stripe82'),
    url(r'^des-pr/(\d+)/(\d+)/(\d+)/(\d+).jpg', 'map.views.map_des_pr'),

    # Catalogs
    url(r'^decals/(\d+)/(\d+)/(\d+)/(\d+).cat.json', 'map.views.cat_decals'),
    url(r'^decals-model/(\d+)/(\d+)/(\d+)/(\d+).cat.json', 'map.views.cat_decals'),
    # brick list of polygons
    url(r'^bricks/', 'map.views.brick_list'),
    # CCD list of polygons
    url(r'^ccds/', 'map.views.ccd_list'),

    # Brick details
    url(r'^brick/(\d{4}[pm]\d{3})', 'map.views.brick_detail', name='brick_detail'),
    # this one is here to provide a name for the javascript to refer to.
    url(r'^brick/', 'map.views.nil', name='brick_detail_blank'),
    # CCD details
    url(r'^ccd/([\w-]+)', 'map.views.ccd_detail', name='ccd_detail'),
    # this one is here to provide a name for the javascript to refer to.
    url(r'^ccd/', 'map.views.nil', name='ccd_detail_blank'),

    # fall-through
    url(r'', 'map.views.index'),
    )
