import numpy as np
#import xarray as xr
import pandas as pd

def theta(x0=120,x1=130,y0=12,y1=10): # TODO : Gérer différemment SH ?
    """
    Computes the angular direction between to points.
    0° corresponds to eastward, 90° northward, 180° westward and 270° southward.

    Parameters
    ----------
    x0: longitude coordinate of the current point
    x1: longitude coordinate of the next point
    y0: latitude coordinate of the current point
    y1: longitude coordinate of the next point

    Returns
    -------
    The directional angle between the current and the next point.
    """
    u = [1,0]
    v = [x1-x0,y1-y0]
    if np.linalg.norm(v) != 0 :
        cos = (x1-x0) / (np.linalg.norm(u) * np.linalg.norm(v)) # Simplification due to u's coordinates
        if cos == -1 :
            th = 180
        else:
            th = np.sign(y1-y0) * np.arccos(cos) * 180 / np.pi
    else :
        th = np.nan
    return np.where(th <0, th + 360, th)

def theta_track(lon, lat):
    """
    Computes the angular direction for each points along a track.
    Handling the track altogether allows for treating stationnary cases as well as the end of the track.

    Parameters
    ----------
    lon: The list of longitudes along the track
    lat: The list of latitude along the track

    Returns
    -------
    th (np.ndarray): values of th along the track.
    """
    th = []
    assert len(lon) == len(lat), "The two vector do not have the same length"
    n = len(lon)
    for i in range(n-1):  # Computing the direction between each point and the following
        th.append(theta(lon[i], lon[i+1], lat[i], lat[i+1]))
        if np.isnan(th[-1]) & (i != 0):  # If two successive points are superimposed, we take the previous direction
            th[-1] = th[-2]
    if n > 1 : th.append(th[-1]); # The direction for the last point is considered the same as the point before
    else : th = [np.nan]
    return th

def theta_multitrack(tracks) :
    """
    Compute the angular direction for every tracks in a dataset

    Parameters
    ----------
    tracks (pd.DataFrame): The set of TC points

    Returns
    -------
    thetas (list): The list of angle for each point in the dataset
    """
    thetas = []
    for id in tracks.track_id.unique():
        track = tracks[tracks.track_id == id]
        th = theta_track(track.lon.values, track.lat.values)
        thetas.append(th)
    return np.concatenate(thetas)

def right_left(field, th):
    """
    Separate geopotential field into left and right of the th line.

    Parameters
    ----------
    field (xr.DataArray): The geopotential field
    th: The direction (in degrees)

    Returns
    -------
    left, right (2 xr.DataArray): The left and right side of the geopt. field.
    """
    if th <= 180 :
        return field.where((field.az<=th) | (field.az>180+th)), field.where((field.az>th) & (field.az<=180+th))
    else :
        return field.where((field.az<=th) & (field.az>th-180)), field.where((field.az>th) | (field.az<=th-180))

def right_left_vector(z, th):
    """
    Separate geopotential field into left and right of the th line.

    Parameters
    ----------
    z (xr.DataArray): The geopotential field
    th: The direction (in degrees)

    Returns
    -------
    left, right (2 xr.DataArray): The left and right side of the z. field.
    """

    A = pd.DataFrame([list(z.az.values)] * len(z.snapshot)) # matrix of az x snapshot
    mask = np.array(A.lt(pd.Series(th % 180), 0) | A.ge((pd.Series(th % 180) + 180), 0)) #Mask in 2D (az, snapshot)
    mask = np.array([mask] * len(z.r)) # Mask in 3D (r, az, snapshot)
    mask = np.swapaxes(mask, 0, 1) # Mask in 3D (az, r, snapshot)
    R, L = z.where(mask), z.where(~mask) # We don't really care if left and right are the wrong way because we only differentiate them afterwards
    return R, L

def area_weights(field) :
    """
    Computes the weights needed for the weighted mean of polar field.

    Parameters
    ----------
    field (xr.DataArray): The geopotential field

    Returns
    -------
    w (xr.DataArray): The weights corresponding to the area wrt the radius.
    """
    δ=(field.r[1] - field.r[0])/2
    w = (field.r +δ) ** 2 - (field.r - δ) ** 2
    return w

def B(th, geopt, SH = False, names=["snap_z900", "snap_z600"]):
    """
    Computes the B parameter for a point, with the corresponding snapshot of geopt at 600hPa and 900hPa

    Parameters
    ----------
    th: The direction (in degrees)
    geopt (xr.DataSet): The snapshots at both levels
    SH (bool): Set to True if the point is in the southern hemisphere
    names: names of the 900hPa and 600hPa geopt. variables in geopt.

    Returns
    -------
    B, the Hart phase space parameter for symetry.
    """
    z900 = geopt[names[0]]
    z600 = geopt[names[1]]
    z900_R, z900_L = right_left(z900, th)
    z600_R, z600_L = right_left(z600, th)
    ΔZ_R = z900_R - z600_R
    ΔZ_L = z900_L - z600_L
    if SH : h = -1;
    else : h=1;
    return  h * (ΔZ_R.weighted(area_weights(ΔZ_R)).mean() - ΔZ_L.weighted(area_weights(ΔZ_L)).mean())

def B_vector(th_vec, geopt, lat, names=["snap_z900", "snap_z600"]):
    """
    Computes the B parameter for a point, with the corresponding snapshot of geopt at 600hPa and 900hPa

    Parameters
    ----------
    th: The direction (in degrees)
    geopt (xr.DataSet): The snapshots at both levels
    SH (bool): Set to True if the point is in the southern hemisphere
    names: names of the 900hPa and 600hPa geopt. variables in geopt.

    Returns
    -------
    B, the Hart phase space parameter for symetry.
    """
    z900 = geopt[names[0]]
    z600 = geopt[names[1]]
    z900_R, z900_L = right_left_vector(z900, th_vec)
    z600_R, z600_L = right_left_vector(z600, th_vec)
    ΔZ_R = z900_R - z600_R
    ΔZ_L = z900_L - z600_L
    h = np.where(lat < 0, -1, 1)
    return h * (ΔZ_R.weighted(area_weights(ΔZ_R)).mean(["az", "r"]) - ΔZ_L.weighted(area_weights(ΔZ_L)).mean(["az", "r"]))

def VT(geopt, names=["snap_z900", "snap_z600", "snap_z300"]):
    """
    Computes V_T^U and V_T^L parameters for the given snapshot of geopt at 300, 600 and 900 hPa

    Parameters
    ----------
    geopt (xr.DataSet): The snapshots at both levels
    names: names of the 900hPa and 600hPa geopt. variables in geopt.

    Returns
    -------
    VTL, VTU
    """
    z900 = geopt[names[0]]
    z600 = geopt[names[1]]
    z300 = geopt[names[2]]
    δz300 = np.abs(z300.max(["r", "az"]) - z300.min(["r", "az"]))
    δz600 = np.abs(z600.max(["r", "az"]) - z600.min(["r", "az"]))
    δz900 = np.abs(z900.max(["r", "az"]) - z900.min(["r", "az"]))
    VTL = 750 * (δz900 - δz600) / (900 - 600)
    VTU = 450 * (δz600 - δz300) / (600 - 300)
    return VTL, VTU

def compute_Hart_parameters(tracks, geopt, names=["snap_z900", "snap_z600", "snap_z300"]):
    """
    Computes the three (+ theta) Hart parameters for all the points in tracks.

    Parameters
    ----------
    tracks (pd.DataFrame): The set of TC points
    geopt (xr.DataSet): The geopotential snapshots associated with the tracks

    Returns
    -------
    tracks (pd.DataFrame): The set of TC points with four new columns corresponding to the parameters
    """

    tracks = tracks.assign(theta=theta_multitrack(tracks))
    tracks = tracks.assign(B=B_vector(tracks.theta.values, geopt, tracks.lat.values, names=names[:-1]))
    VTL, VTU = VT(geopt, names = names)
    tracks = tracks.assign(VTL=VTL, VTU = VTU)

    return tracks