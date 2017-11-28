import os
import glob
from astropy.io import fits
import numpy as np


def ISR_main(dirtarget, dirdark, target):
    """Creates ISR FITS files by executing a preliminary calibration sequence.

    Imports and calls get_unfiltered_calibimages, get_filtered_calibimages, and
    instrument_signature_removal. Saves ISR science images to
    dirtarget/ISR_Images/<filter-name>.

    Parameters
    ----------
    dirtarget : str
        Directory containing all bias, flat, and raw science images.
    dirdark : str
        Directory containing all dark images.
    traget : str
        Name of target.

    Returns
    -------
    image_filters : list
        List containing string of each filter keyword found in header of flat 
        field and light frame images.
    """
    # Creates and saves master bias, dark and flat by filter.
    exptime = get_unfiltered_calibimages(dirtarget, dirdark)
    image_filters = get_filtered_calibimages(dirtarget)

    # Creates and saves instrument-siganture-removed light frames.
    instrument_signature_removal(dirtarget, target, exptime, image_filters)

    return image_filters


def get_unfiltered_calibimages(dirtarget, dirdark):
    """Creates and saves master bias and dark.

    Searches in dirtarget for all bias frames and creates master bias by taking
    the median of the array of those images. It then saves the master bias to
    dirtarget/mcalib. It then searches in dirdark for all dark frames and
    subtracts the mbias and time-corrects each image. It then creates the
    master dark by taking the median of the array of those images. It then
    saves the master dark to dirtarget/mcalib.

    Parameters
    ----------
    dirtarget : str
        Directory containing all bias, flat, and science images.
    dirdark : str
        Directory containing all dark images.

    Returns
    -------
    exptime : float
        Exposure time of light frames in seconds.
    """
    # Retrieves all FITS files from dirtarget and dark frames from dirdark.
    t_files = glob.glob(os.path.join(dirtarget, '*.fit'))
    d_files = glob.glob(os.path.join(dirdark, '*.fit'))
    os.mkdir(dirtarget + '/mcalib')

    biases = []
    bias_prihdr = None
    darks = []
    dark_prihdr = None
    dark_exptime = None
    exptime = None

    # Retrieves all bias frames and creates master bias.
    for o_file in t_files:
        hdulist = fits.open(o_file)
        if hdulist[0].header['IMAGETYP'] == 'Bias Frame':
            biases.append(fits.getdata(o_file))
            bias_prihdr = hdulist[0].header
        if hdulist[0].header['IMAGETYP'] == 'Light Frame':
            exptime = hdulist[0].header['EXPTIME']
        hdulist.close()

    bias_array = np.array(biases, dtype=float)

    mbias_array = np.median(bias_array, 0)

    # Saves master bias to mcalib.
    hdu = fits.PrimaryHDU(mbias_array, header=bias_prihdr)
    hdulist = fits.HDUList([hdu])
    hdulist.writeto(dirtarget + '/mcalib/mbias.fits')

    # Retrieves all dark frames from dirdark as well as .
    for o_file in d_files:
        hdulist = fits.open(o_file)
        if hdulist[0].header['IMAGETYP'] == 'Dark Frame':
            darks.append(fits.getdata(o_file))
            dark_exptime = hdulist[0].header['EXPTIME']
            dark_prihdr = hdulist[0].header

    dark_array = np.array(darks, dtype=float)

    for dark in dark_array:
        dark -= mbias_array
        dark /= dark_exptime
        print(dark)
        print(exptime)
        dark = *= exptime

    mdark = np.median(dark_array, 0)

    # Saves master dark.
    hdu = fits.PrimaryHDU(mdark, header=dark_prihdr)
    hdulist = fits.HDUList([hdu])
    hdulist.writeto(dirtarget + '/mcalib/mdark.fits', overwrite=True)

    return exptime


def get_filtered_calibimages(dirtarget):
    """Creates and saves master flat for each filter.

    Creates a list of all unique filter names on flat and light images. It then
    loops through that list looking for all flatswith the same filter name for
    each iteration of the loop. It then subtracts the bias and normalizes each
    individual flat and averages that array. The master flat is then saved as
    "<filter-name>_mflat.fits" to dirtarget/mcalib.

    Parameters
    ----------
    dirtarget : str
        Directory containing all bias, flat, and science images.

    Returns
    -------
    image_filters : list
        List containing string of each filter keyword found in header of flat 
        field and light frame images.
    """
    image_filters = set()
    mbias = []

    # Retrive all FITS files from dataset and master calibration files.
    files = glob.glob(os.path.join(dirtarget, '*.fit'))
    calib_files = glob.glob(os.path.join(dirtarget + '/mcalib/', '*.fits'))

    # Retrieve master bias.
    for o_file in calib_files:
        hdulist = fits.open(o_file)
        if hdulist[0].header['IMAGETYP'] == 'Bias Frame':
            mbias.append(fits.getdata(o_file))
        hdulist.close()

    mbias_array = np.array(mbias, dtype=float)

    # Retrieve all filter types used on dataset.
    for o_file in files:
        hdulist = fits.open(o_file)
        if (hdulist[0].header['IMAGETYP'] == 'Flat Field' or
                hdulist[0].header['IMAGETYP'] == 'Light Frame'):
            image_filters.add(hdulist[0].header['FILTER'])
        hdulist.close()

    for i in image_filters:
        flats = []
        flat_prihdr = None
        # Retrieves flats with the same filter name.
        for o_file in files:
            hdulist = fits.open(o_file)
            if (hdulist[0].header['IMAGETYP'] == 'Flat Field' and
                    hdulist[0].header['FILTER'] == i):
                flats.append(fits.getdata(o_file))
                flat_prihdr = hdulist[0].header
            hdulist.close()

        flat_array = np.array(flats, dtype=float)

        # Removes bias from and normalizes each flat.
        for flat in flat_array:
            flat -= mbias_array[0]
            flat /= np.average(flat[700:1348, 450:3622])

        mflat = np.average(flat_array, 0)

        # Saves master flat.
        hdu = fits.PrimaryHDU(mflat, header=flat_prihdr)
        hdulist = fits.HDUList([hdu])
        hdulist.writeto(dirtarget + '/mcalib/' + i + '_mflat.fits',
                        overwrite=True)

    return image_filters


def instrument_signature_removal(dirtarget, target, exptime, image_filters):
    """Removes instrument signatures from raw science images.

    Retrieves all FITS files with IMAGETYP keyword, "Light Frame" and all
    master calibration images and puts them into arrays. It then calculates the
    expected saturation, which is later added to the header. It then removes
    the master bias, dark, and flat by filer from each image in the light frame
    array and saves it as a FITS file with the light frame header as dirtarget/
    ISR_Images/<filter-name>/<target-name>_<filter-keyword>_*.fits

    Parameters
    ----------
    dirtarget : str
        Directory containing all bias, flat, and raw science images.
    target : str
        Name of target.
    exptime : float
        Exposure time of light frames in seconds.
    image_filters : list
        List containing string of each filter keyword found in header of flat 
        field and light frame images.

    Returns
    -------
    None
    """
    mflat = []
    mbias = []
    mdark = []
    dark_exptime = None
    for fil in image_filters:
        # Gets mbias, mdark, and mflat of correct filter from mcalib.
        for path in os.listdir(os.path.join(dirtarget, 'mcalib')):
            if path.endswith(".fits"):
                o_path = os.path.join(dirtarget, 'mcalib', path)
                calib_file = fits.open(o_path)
                if calib_file[0].header['IMAGETYP'] == 'Bias Frame':
                    mbias.append(calib_file[0].data)
                if calib_file[0].header['IMAGETYP'] == 'Dark Frame':
                    dark_exptime = calib_file[0].header['EXPTIME']
                    mdark.append(calib_file[0].data)
                if calib_file[0].header['IMAGETYP'] == 'Flat Field':
                    if calib_file[0].header['FILTER'] == fil:
                        mflat.append(calib_file[0].data)
                calib_file.close()
                
        mbias_array = np.array(mbias, dtype=float)
        mdark_array = np.array(mdark, dtype=float)
        mflat_array = np.array(mflat, dtype=float)

        mbias_array = mbias_array[0]
        mdark_array = mdark_array[0]
        mflat_array = mflat_array[0]

        # Calculates expected saturation of image.
        saturation = 65535
        saturation -= np.median(mbias_array)
        saturation -= np.median((mdark_array*exptime)/dark_exptime)
        saturation /= np.average(mflat_array)
        saturation *= 0.97
        saturation = int(saturation)

        # Makes directory for each filter to write ISR files to.
        os.mkdir(os.path.join(dirtarget, 'ISR_Images'))
        os.mkdir(os.path.join(dirtarget, 'ISR_Images', fil))
        # Finds all light frame images in dirtarget of correct filter.
        for n, path in enumerate(os.listdir(dirtarget)):
            if path.endswith(".fit"):
                o_file = os.path.join(dirtarget, path)
                hdulist = fits.open(o_file)
                if hdulist[0].header['IMAGETYP'] == 'Light Frame':
                    if hdulist[0].header['FILTER'] == fil:
                        # Adds saturation to header.
                        hdulist[0].header['SATLEVEL'] = saturation
                        prihdr = hdulist[0].header
                        image = hdulist[0].data
                        image_array = np.array(image, dtype=float)
                        # Removes instrument signatures.
                        image_array -= mbias_array
                        image_array -= mdark_array
                        image_array /= mflat_array
                        # Writes ISR file.
                        hdu = fits.PrimaryHDU(image_array, header=prihdr)
                        hdulist = fits.HDUList([hdu])
                        out_path = os.path.join(dirtarget, 'ISR_Images', fil,
                                                target + '_' + fil +
                                                '_{}'.format(n) + '.fits')
                        hdulist.writeto(out_path, overwrite=True) 
