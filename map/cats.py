from __future__ import print_function
import os
import fitsio
from django.http import HttpResponse, StreamingHttpResponse
from decals import settings
from django.core.urlresolvers import reverse
from map.utils import send_file, trymakedirs, get_tile_wcs, oneyear


debug = print
if not settings.DEBUG_LOGGING:
    def debug(*args, **kwargs):
        pass

catversions = {
    'mzls+bass-dr6': [1,],
    'decals-dr5': [1,],
    'mzls+bass-dr4': [1,],
    'decals-dr2': [2,],
    'decals-dr3': [1,],
    'ngc': [1,],
    'spec': [1,],
    'spec-deep2': [1,],
    'bright': [1,],
    'tycho2': [1,],
    'targets-dr2': [1,],
    'targets-dr45': [1,],
    'gaia-dr1': [1,],
    'phat-clusters': [1,],
    'ps1': [1,],
}

def cat_phat_clusters(req, ver):
    import json
    from astrometry.util.fits import fits_table, merge_tables

    tag = 'phat-clusters'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    cat = fits_table(os.path.join(settings.DATA_DIR, 'phat-clusters.fits'))
    cat.cut((cat.ra  >= ralo ) * (cat.ra  <= rahi) *
            (cat.dec >= declo) * (cat.dec <= dechi))

    return HttpResponse(json.dumps(dict(
        name=[str(s.strip()) for s in cat.name],
        rd=[(float(o.ra),float(o.dec)) for o in cat],
        mag=[float(o.mag) for o in cat],
        young=[bool(o.young) for o in cat],
        velocity=[float(o.velocity) for o in cat],
        metallicity=[float(o.metallicity) for o in cat],
    )),
                        content_type='application/json')


def cat_gaia_dr1(req, ver):
    import json
    from legacyanalysis.gaiacat import GaiaCatalog

    tag = 'gaia-dr1'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    os.environ['GAIA_CAT_DIR'] = settings.GAIA_CAT_DIR
    gaia = GaiaCatalog()
    cat = gaia.get_catalog_radec_box(ralo, rahi, declo, dechi)

    return HttpResponse(json.dumps(dict(
                rd=[(float(o.ra),float(o.dec)) for o in cat],
                gmag=[float(o.phot_g_mean_mag) for o in cat],
                )),
                        content_type='application/json')

def upload_cat(req):
    import tempfile
    from astrometry.util.fits import fits_table
    from django.http import HttpResponseRedirect
    from map.views import index

    if req.method != 'POST':
        return HttpResponse('POST only')
    print('Files:', req.FILES)
    cat = req.FILES['catalog']

    dirnm = settings.USER_QUERY_DIR
    if not os.path.exists(dirnm):
        try:
            os.makedirs(dirnm)
        except:
            pass
    f,tmpfn = tempfile.mkstemp(suffix='.fits', dir=dirnm)
    os.close(f)
    os.unlink(tmpfn)
    print('Saving to', tmpfn)
    with open(tmpfn, 'wb+') as destination:
        for chunk in cat.chunks():
            destination.write(chunk)    
    print('Wrote', tmpfn)

    try:
        T = fits_table(tmpfn)
    except:
        return HttpResponse('Must upload FITS format catalog including "RA", "Dec", optionally "Name" columns')
    cols = T.columns()
    if not (('ra' in cols) and ('dec' in cols)):
        return HttpResponse('Must upload catalog including "RA", "Dec", optionally "Name" columns')

    ra,dec = T.ra[0], T.dec[0]
    catname = tmpfn.replace(dirnm, '').replace('.fits', '')
    if catname.startswith('/'):
        catname = catname[1:]

    try:
        import fitsio
        primhdr = fitsio.read_header(tmpfn)
        name = primhdr.get('CATNAME', '')
        color = primhdr.get('CATCOLOR', '')
        if len(name):
            catname = catname + '-n%s' % name.strip().replace(' ','_')
        if len(color):
            catname = catname + '-c%s' % color.strip()
    except:
        pass
    
    return HttpResponseRedirect(reverse(index) +
                                '?ra=%.4f&dec=%.4f&catalog=%s' % (ra, dec, catname))

def get_random_galaxy(layer=None):
    import numpy as np
    from map.views import galaxycat

    global galaxycat
    #galfn = os.path.join(settings.DATA_DIR, 'galaxy-cats-in-dr2.fits')
    if layer == 'mzls+bass-dr4':
        galfn = os.path.join(settings.DATA_DIR, 'galaxies-in-dr4.fits')
        drnum = 4
    else:
        galfn = os.path.join(settings.DATA_DIR, 'galaxies-in-dr3.fits')
        drnum = 3

    if galaxycat is None and not os.path.exists(galfn):
        if settings.CREATE_GALAXY_CATALOG:
            try:
                create_galaxy_catalog(galfn, drnum)
            except:
                pass
        if not os.path.exists(galfn):
            if drnum == 4:
                return 147.1744, 44.0812, 'NGC 2998'
            else:
                return 18.6595, -1.0210, 'NGC 442'

    if galaxycat is None:
        from astrometry.util.fits import fits_table
        galaxycat = fits_table(galfn)

    i = np.random.randint(len(galaxycat))
    ra = float(galaxycat.ra[i])
    dec = float(galaxycat.dec[i])
    name = galaxycat.name[i].strip()
    return ra,dec,name

def create_galaxy_catalog(galfn, drnum):
    import astrometry.catalogs
    from astrometry.util.fits import fits_table, merge_tables
    import fitsio
    from astrometry.util.util import Tan

    fn = os.path.join(os.path.dirname(astrometry.catalogs.__file__), 'ngc2000.fits')
    NGC = fits_table(fn)
    print(len(NGC), 'NGC objects')
    NGC.name = np.array(['NGC %i' % n for n in NGC.ngcnum])
    NGC.delete_column('ngcnum')
    
    fn = os.path.join(os.path.dirname(astrometry.catalogs.__file__), 'ic2000.fits')
    IC = fits_table(fn)
    print(len(IC), 'IC objects')
    IC.name = np.array(['IC %i' % n for n in IC.icnum])
    IC.delete_column('icnum')

    # fn = os.path.join(settings.DATA_DIR, 'ugc.fits')
    # UGC = fits_table(fn)
    # print(len(UGC), 'UGC objects')
    # UGC.name = np.array(['UGC %i' % n for n in UGC.ugcnum])
    # UGC.delete_column('ugcnum')

    #T = merge_tables([NGC, IC, UGC])
    #T.writeto(os.path.join(settings.DATA_DIR, 'galaxy-cats.fits'))

    T = merge_tables([NGC, IC])
    T.writeto(os.path.join('/tmp/galaxy-cats.fits'))
    
    keep = np.zeros(len(T), bool)

    if drnum == 3:
        bricks = fits_table(os.path.join(settings.DATA_DIR, 'decals-dr3',
                                         'decals-bricks-in-dr3.fits'))
        bricks.cut(bricks.has_g * bricks.has_r * bricks.has_z)
        print(len(bricks), 'bricks with grz')
        from map.views import _get_survey
        survey = _get_survey('decals-dr3')
    elif drnum == 4:
        from map.views import _get_survey
        survey = _get_survey('mzls+bass-dr4')

        bricks = fits_table(os.path.join(settings.DATA_DIR, 'survey-bricks-in-dr4.fits'))

        # bricks = fits_table(os.path.join(settings.DATA_DIR, 'survey-bricks-dr4.fits'))
        # bricks.cut((bricks.nexp_g > 0) *
        #            (bricks.nexp_r > 0) *
        #            (bricks.nexp_z > 0))
        # print(len(bricks), 'bricks with grz')
        # 
        # sbricks = survey.get_bricks()
        # binds = dict([(b,i) for i,b in enumerate(sbricks.brickname)])
        # I = np.array([binds[b] for b in bricks.brickname])
        # bricks.ra1  = sbricks.ra1[I]
        # bricks.ra2  = sbricks.ra2[I]
        # bricks.dec1 = sbricks.dec1[I]
        # bricks.dec2 = sbricks.dec2[I]
        # 
        # fn = '/tmp/survey-bricks-in-dr4.fits'
        # bricks.writeto(fn)
        # print('Wrote', fn)


    for brick in bricks:
        fn = survey.find_file('nexp', brick=brick.brickname, band='r')
        if not os.path.exists(fn):
            print('Does not exist:', fn)
            continue

        I = np.flatnonzero((T.ra  >= brick.ra1 ) * (T.ra  < brick.ra2 ) *
                           (T.dec >= brick.dec1) * (T.dec < brick.dec2))
        print('Brick', brick.brickname, 'has', len(I), 'galaxies')
        if len(I) == 0:
            continue

        nn,hdr = fitsio.read(fn, header=True)
        h,w = nn.shape
        #imgfn = survey.find_file('image', brick=brick.brickname, band='r')
        #wcs = Tan(imgfn)
        print('file', fn)
        wcs = Tan(hdr)

        ok,x,y = wcs.radec2pixelxy(T.ra[I], T.dec[I])
        x = np.clip((x-1).astype(int), 0, w-1)
        y = np.clip((y-1).astype(int), 0, h-1)
        n = nn[y,x]
        keep[I[n > 0]] = True

    T.cut(keep)
    fn = '/tmp/galaxies-in-dr%i.fits' % drnum
    T.writeto(fn)
    print('Wrote', fn)
    T.writeto(galfn)

def cat_targets_dr2(req, ver):
    import json
    tag = 'targets-dr2'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np
    from cat.models import DR2_Target as Target

    from astrometry.util.starutil_numpy import radectoxyz, xyztoradec, degrees_between
    xyz1 = radectoxyz(ralo, declo)
    xyz2 = radectoxyz(rahi, dechi)
    xyz = (xyz1 + xyz2)/2.
    xyz /= np.sqrt(np.sum(xyz**2))
    rc,dc = xyztoradec(xyz)
    rc = rc[0]
    dc = dc[0]
    rad = degrees_between(rc, dc, ralo, declo)

    objs = Target.objects.extra(where=[
            'q3c_radial_query(target.ra, target.dec, %.4f, %.4f, %g)'
            % (rc, dc, rad * 1.01)])
    print('Got', objs.count(), 'targets')
    print('types:', np.unique([o.type for o in objs]))
    print('versions:', np.unique([o.version for o in objs]))

    return HttpResponse(json.dumps(dict(
                rd=[(float(o.ra),float(o.dec)) for o in objs],
                name=[o.type for o in objs],
                )),
                        content_type='application/json')

def cat_targets_dr45(req, ver):
    import json
    tag = 'targets-dr45'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table, merge_tables
    from astrometry.libkd.spherematch import tree_open, tree_search_radec
    import numpy as np
    from astrometry.util.starutil_numpy import radectoxyz, xyztoradec, degrees_between

    xyz1 = radectoxyz(ralo, declo)
    xyz2 = radectoxyz(rahi, dechi)
    xyz = (xyz1 + xyz2)/2.
    xyz /= np.sqrt(np.sum(xyz**2))
    rc,dc = xyztoradec(xyz)
    rc = rc[0]
    dc = dc[0]
    rad = degrees_between(rc, dc, ralo, declo)

    '''
    startree -i /project/projectdirs/desi/target/catalogs/targets-dr5-0.16.2.fits -o /tmp/kd.fits -P -k
    fitsgetext -i /tmp/kd.fits -o targets-dr5-0.16.2.kd.fits -e 0 -e 6 -e 1 -e 2 -e 3 -e 4 -e 5
    '''
    TT = []
    for fn in [os.path.join(settings.DATA_DIR, 'targets-dr5-0.17.1.kd.fits'),
               os.path.join(settings.DATA_DIR, 'targets-dr4-0.17.1.kd.fits'),
               ]:
        kd = tree_open(fn)
        I = tree_search_radec(kd, rc, dc, rad)
        print('Matched', len(I), 'from', fn)
        if len(I) == 0:
            continue
        T = fits_table(fn, rows=I)
        TT.append(T)
    if len(TT) == 0:
        return HttpResponse(json.dumps(dict(rd=[], name=[])),
                            content_type='application/json')
    T = merge_tables(TT)

    names = []
    colors = []
    for t in T:
        desibits = []
        bgsbits = []
        mwsbits = []
        for bit in range(64):
            if (1 << bit) & int(t.desi_target):
                desibits.append(bit)
            if (1 << bit) & int(t.bgs_target):
                bgsbits.append(bit)
            if (1 << bit) & int(t.mws_target):
                mwsbits.append(bit)
        # https://github.com/desihub/desitarget/blob/master/py/desitarget/data/targetmask.yaml
        desinames = [{
            0:  'LRG',
            1:  'ELG',
            2:  'QSO',
            # 8:  'LRG_NORTH',
            # 9:  'ELG_NORTH',
            # 10: 'QSO_NORTH',
            # 16: 'LRG_SOUTH',
            # 17: 'ELG_SOUTH',
            # 18: 'QSO_SOUTH',
            32: 'SKY',
            33: 'STD_FSTAR',
            34: 'STD_WD',
            35: 'STD_BRIGHT',
            36: 'BADSKY',
            50: 'BRIGHT_OBJECT',
            51: 'IN_BRIGHT_OBJECT',
            52: 'NEAR_BRIGHT_OBJECT',
            # 60: 'BGS_ANY',
            # 61: 'MWS_ANY',
            62: 'ANCILLARY_ANY',
        }.get(b) for b in desibits]
        bgsnames = [{
            0:  'BGS_FAINT',
            1:  'BGS_BRIGHT',
            # 8:  'BGS_FAINT_NORTH',
            # 9:  'BGS_BRIGHT_NORTH',
            # 16: 'BGS_FAINT_SOUTH',
            # 17: 'BGS_BRIGHT_SOUTH',
            40: 'BGS_KNOWN_ANY',
            41: 'BGS_KNOWN_COLLIDED',
            42: 'BGS_KNOWN_SDSS',
            43: 'BGS_KNOWN_BOSS',
        }.get(b) for b in bgsbits]
        mwsnames = [{
            0:  'MWS_MAIN',
            1:  'MWS_WD',
            2:  'MWS_NEARBY',
            16: 'MWS_MAIN_VERY_FAINT',
        }.get(b) for b in mwsbits]

        bitnames = [n for n in desinames + bgsnames + mwsnames if n is not None]

        names.append(', '.join(bitnames))

        nn = ' '.join(bitnames)
        cc = 'white'
        if 'QSO' in nn:
            cc = 'cyan'
        elif 'LRG' in nn:
            cc = 'red'
        elif 'ELG' in nn:
            cc = 'gray'
        elif 'BGS' in nn:
            cc = 'orange'
        colors.append(cc)

    return HttpResponse(json.dumps(dict(rd=[(t.ra, t.dec) for t in T],
                                        name=names,
                                        targetid=[int(t) for t in T.targetid],
                                        fluxes=[dict(g=float(g), r=float(r), z=float(z),
                                                     W1=float(W1), W2=float(W2))
                                                for (g,r,z,W1,W2)
                                                in zip(T.flux_g, T.flux_r, T.flux_z,
                                                       T.flux_w1, T.flux_w2)],
                                        nobs=[dict(g=int(g), r=int(r), z=int(z)) for g,r,z
                                              in zip(T.nobs_g, T.nobs_r, T.nobs_z)],
                                        color=colors,
                                    )),
                        content_type='application/json')

def cat_spec(req, ver):
    import json
    tag = 'spec'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np

    TT = []
    T = fits_table(os.path.join(settings.DATA_DIR, 'specObj-dr12-trim-2.fits'))
    debug(len(T), 'spectra')
    if ralo > rahi:
        # RA wrap
        T.cut(np.logical_or(T.ra > ralo, T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    else:
        T.cut((T.ra > ralo) * (T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    debug(len(T), 'in cut')

    rd = list((float(r),float(d)) for r,d in zip(T.ra, T.dec))
    names = [t.strip() for t in T.label]

    # HACK
    #names = [t.split()[0] for t in names]

    mjd   = [int(x) for x in T.mjd]
    fiber = [int(x) for x in T.fiberid]
    plate = [int(x) for x in T.plate]

    return HttpResponse(json.dumps(dict(rd=rd, name=names, mjd=mjd, fiber=fiber, plate=plate)),
                        content_type='application/json')


def cat_spec_deep2(req, ver):
    import json
    tag = 'spec-deep2'
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])
    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np

    TT = []
    T = fits_table(os.path.join(settings.DATA_DIR, 'deep2-zcat-dr4-uniq.fits'))
    debug(len(T), 'spectra')
    if ralo > rahi:
        # RA wrap
        T.cut(np.logical_or(T.ra > ralo, T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    else:
        T.cut((T.ra > ralo) * (T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    debug(len(T), 'in cut')

    rd = list((float(r),float(d)) for r,d in zip(T.ra, T.dec))
    names = []

    classes = T.get('class')
    subclasses = T.subclass
    zbests = T.zbest
    zq = T.zquality
    for i in range(len(T)):
        clazz = classes[i]
        clazz = clazz[0] + clazz[1:].lower()

        #if zq[i] >= 3:
        nm = clazz
        sc = subclasses[i].strip()
        if sc != 'NONE':
            nm += ' ' + sc
        if not (zq[i] == -1 and clazz.strip() == 'Star'):
            nm += ' z=%.2f, q=%i' % (zbests[i], zq[i])
        names.append(nm)

    return HttpResponse(json.dumps(dict(rd=rd, name=names)),
                        content_type='application/json')

def cat_user(req, ver):
    from astrometry.util.fits import fits_table
    import json
    import re

    cat = str(req.GET.get('cat'))
    if not re.match('\w?', cat):
        print('Catalog "%s" did not match regex' % cat)
        return

    haverd = False
    havei = False
    
    if ('ralo'  in req.GET and 'rahi'  in req.GET and
        'declo' in req.GET and 'dechi' in req.GET):
        ralo = float(req.GET['ralo'])
        rahi = float(req.GET['rahi'])
        declo = float(req.GET['declo'])
        dechi = float(req.GET['dechi'])
        haverd = True
    elif ('start' in req.GET and 'N' in req.GET):
        start = int(req.GET['start'])
        N = int(req.GET['N'])
        havei = True
    else:
        return HttpResponse('need {ra,dec}{lo,hi} or start,N')
    
    fn = os.path.join(settings.USER_QUERY_DIR, cat+'.fits')
    if not os.path.exists(fn):
        return
    cat = fits_table(fn)
    if haverd:
        if ralo > rahi:
            import numpy as np
            # RA wrap
            cat.cut(np.logical_or(cat.ra > ralo, cat.ra < rahi) *
                    (cat.dec > declo) * (cat.dec < dechi))
        else:
            cat.cut((cat.ra > ralo) * (cat.ra < rahi) *
            (cat.dec > declo) * (cat.dec < dechi))
        print(len(cat), 'user catalog sources after RA,Dec cut')
    elif havei:
        cat = cat[start:start+N]

    rd = list(zip(cat.ra.astype(float), cat.dec.astype(float)))

    D = dict(rd=rd)
    cols = cat.columns()
    if 'name' in cols:
        D.update(names=list(cat.name))
    if 'type' in cols:
        D.update(sourcetype=list([t[0] for t in cat.get('type')]))
    if 'g' in cols and 'r' in cols and 'z' in cols:
        D.update(fluxes=[dict(g=float(g), r=float(r), z=float(z))
                         for g,r,z in zip(10.**((cat.g - 22.5)/-2.5),
                                          10.**((cat.r - 22.5)/-2.5),
                                          10.**((cat.z - 22.5)/-2.5))])
    if 'gnobs' in cols and 'rnobs' in cols and 'znobs' in cols:
        D.update(nobs=[dict(g=int(g), r=int(r), z=int(z))
                       for g,r,z in zip(cat.gnobs, cat.rnobs, cat.znobs)])
    if 'objids' in cols:
        D.update(objids=[int(x) for x in cat.objid])
    if 'brickname' in cols:
        D.update(bricknames=list(cat.brickname))
    if 'radius' in cols:
        D.update(radius=list([float(r) for r in cat.radius]))
    if 'color' in cols:
        D.update(color=list([c.strip() for c in cat.color]))

    return HttpResponse(json.dumps(D).replace('NaN','null'),
                        content_type='application/json')

def cat_bright(req, ver):
    return cat(req, ver, 'bright',
               os.path.join(settings.DATA_DIR, 'bright.fits'))

def cat_tycho2(req, ver):
    return cat(req, ver, 'tycho2',
               os.path.join(settings.DATA_DIR, 'tycho2.fits'))

def cat_gals(req, ver):
    return cat(req, ver, 'ngc',
               os.path.join(settings.DATA_DIR,'galaxy-cats.fits'))

def cat_ps1(req, ver):
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])
    # We have the EDR region and a block around 0,0
    if (rahi > 241) and (ralo < 246) * (dechi >= 6.5) * (declo < 11.5):
        return cat(req, ver, 'ps1',
                   os.path.join(settings.DATA_DIR,'ps1-cat-edr.fits'))
    return cat(req, ver, 'ps1',
               os.path.join(settings.DATA_DIR,'ps1-cat.fits'))

def cat(req, ver, tag, fn):
    import json
    ralo = float(req.GET['ralo'])
    rahi = float(req.GET['rahi'])
    declo = float(req.GET['declo'])
    dechi = float(req.GET['dechi'])

    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    from astrometry.util.fits import fits_table
    import numpy as np

    TT = []
    T = fits_table(fn)
    debug(len(T), 'catalog objects')
    if ralo > rahi:
        # RA wrap
        T.cut(np.logical_or(T.ra > ralo, T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    else:
        T.cut((T.ra > ralo) * (T.ra < rahi) * (T.dec > declo) * (T.dec < dechi))
    debug(len(T), 'in cut')

    rd = list((float(r),float(d)) for r,d in zip(T.ra, T.dec))
    rtn = dict(rd=rd)

    # PS1
    if 'ndetections' in T.columns():
        T.name = np.array(['%i' % n for n in T.ndetections])

    if 'name' in T.columns():
        names = [t.strip() for t in T.name]
        rtn['name'] = names
    # bright stars
    if 'alt_name' in T.columns():
        rtn.update(altname = [t.strip() for t in T.alt_name])
    if 'radius' in T.columns():
        rtn.update(radiusArcsec=list(float(f) for f in T.radius * 3600.))
        
    return HttpResponse(json.dumps(rtn), content_type='application/json')

def cat_decals_dr2(req, ver, zoom, x, y, tag='decals-dr2'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_decals_dr3(req, ver, zoom, x, y, tag='decals-dr3'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_mobo_dr4(req, ver, zoom, x, y, tag='mzls+bass-dr4'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_decals_dr5(req, ver, zoom, x, y, tag='decals-dr5'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_mobo_dr6(req, ver, zoom, x, y, tag='mzls+bass-dr6'):
    return cat_decals(req, ver, zoom, x, y, tag=tag, docache=False)

def cat_decals(req, ver, zoom, x, y, tag='decals', docache=True):
    import json
    zoom = int(zoom)
    if zoom < 12:
        return HttpResponse(json.dumps(dict(rd=[])),
                            content_type='application/json')

    from astrometry.util.fits import fits_table, merge_tables
    import numpy as np

    try:
        wcs, W, H, zoomscale, zoom,x,y = get_tile_wcs(zoom, x, y)
    except RuntimeError as e:
        print('e:', e)
        return HttpResponse(e.strerror)
    ver = int(ver)
    if not ver in catversions[tag]:
        raise RuntimeError('Invalid version %i for tag %s' % (ver, tag))

    basedir = settings.DATA_DIR
    sendfile_kwargs = dict()
    if docache:
        cachefn = os.path.join(basedir, 'cats-cache', tag,
                               '%i/%i/%i/%i.cat.json' % (ver, zoom, x, y))
        if os.path.exists(cachefn):
            return send_file(cachefn, 'application/json',
                             modsince=req.META.get('HTTP_IF_MODIFIED_SINCE'),
                             expires=oneyear)
        sendfile_kwargs.update(expires=oneyear)
    else:
        import tempfile
        f,cachefn = tempfile.mkstemp(suffix='.json')
        os.close(f)
        sendfile_kwargs.update(unlink=True)

    cat,hdr = _get_decals_cat(wcs, tag=tag)

    if cat is None:
        rd = []
        types = []
        fluxes = []
        bricknames = []
        objids = []
        nobs = []
    else:
        rd = list(zip(cat.ra, cat.dec))
        types = list([t[0] for t in cat.get('type')])

        if 'decam_flux' in cat.get_columns():
            fluxes = [dict(g=float(g), r=float(r), z=float(z))
                      for g,r,z in zip(cat.decam_flux[:,1], cat.decam_flux[:,2],
                                       cat.decam_flux[:,4])]
            nobs = [dict(g=int(g), r=int(r), z=int(z))
                    for g,r,z in zip(cat.decam_nobs[:,1], cat.decam_nobs[:,2],
                                     cat.decam_nobs[:,4])]
        else:
            # DR4+
            fluxes = [dict(g=float(g), r=float(r), z=float(z))
                      for g,r,z in zip(cat.flux_g, cat.flux_r, cat.flux_z)]
            nobs = [dict(g=int(g), r=int(r), z=int(z))
                    for g,r,z in zip(cat.nobs_g, cat.nobs_r, cat.nobs_z)]

        bricknames = list(cat.brickname)
        objids = [int(x) for x in cat.objid]

    json = json.dumps(dict(rd=rd, sourcetype=types, fluxes=fluxes, nobs=nobs,
                                 bricknames=bricknames, objids=objids))
    if docache:
        trymakedirs(cachefn)

    f = open(cachefn, 'w')
    f.write(json)
    f.close()
    return send_file(cachefn, 'application/json', **sendfile_kwargs)

def _get_decals_cat(wcs, tag='decals'):
    from astrometry.util.fits import fits_table, merge_tables
    from map.views import _get_survey

    basedir = settings.DATA_DIR
    H,W = wcs.shape
    X = wcs.pixelxy2radec([1,1,1,W/2,W,W,W,W/2],
                            [1,H/2,H,H,H,H/2,1,1])
    r,d = X[-2:]

    #catpat = os.path.join(basedir, 'cats', tag, '%(brickname).3s',
    #                      'tractor-%(brickname)s.fits')

    survey = _get_survey(name=tag)
    B = survey.get_bricks_readonly()
    I = survey.bricks_touching_radec_box(B, r.min(), r.max(), d.min(), d.max())
    #print(len(I), 'bricks touching RA,Dec box', r.min(),r.max(), d.min(),d.max())

    cat = []
    hdr = None
    for brickname in B.brickname[I]:
        catfn = survey.find_file('tractor', brick=brickname)
        if not os.path.exists(catfn):
            print('Does not exist:', catfn)
            continue
        debug('Reading catalog', catfn)
        T = fits_table(catfn)
        T.cut(T.brick_primary)
        print('File', catfn, 'cut to', len(T), 'primary')
        ok,xx,yy = wcs.radec2pixelxy(T.ra, T.dec)
        T.cut((xx > 0) * (yy > 0) * (xx < W) * (yy < H))
        cat.append(T)
        if hdr is None:
            hdr = T.get_header()
    if len(cat) == 0:
        cat = None
    else:
        cat = merge_tables(cat, columns='fillzero')

    return cat,hdr



if __name__ == '__main__':
    print('Random galaxy:', get_random_galaxy(layer='mzls+bass-dr4'))
