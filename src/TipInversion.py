# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Haseeb Zia on Tue Nov  1 15:22:00 2016.
Copyright (c) "ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory", 2016-2017. All rights
reserved. See the LICENSE.TXT file for more details.

Tip inversion for different flow regimes. The functions take width opening and gives distance from tip calculated using
the given propagation regime
"""

# imports
import math
import numpy as np
from scipy.optimize import brentq
from src.Utility import *
import matplotlib.pyplot as plt
import warnings

def TipAsym_viscStor_Res(dist, *args):
    """Residual function for viscocity dominate regime, without leak off"""

    (wEltRibbon, Kprime, Eprime, muPrime, Cbar, DistLstTSEltRibbon, dt) = args
    return wEltRibbon - (18 * 3 ** 0.5 * (dist - DistLstTSEltRibbon) / dt * muPrime / Eprime) ** (1 / 3) * dist ** (
        2 / 3)


# ----------------------------------------------------------------------------------------------------------------------

def TipAsym_viscLeakOff_Res(dist, *args):
    """Residual function for viscosity dominated regime, with leak off"""
    (wEltRibbon, Kprime, Eprime, muPrime, Cbar, DistLstTSEltRibbon, dt) = args
    return wEltRibbon - 4 / (15 * np.tan(np.pi / 8)) ** 0.25 * (Cbar * muPrime / Eprime) ** 0.25 * ((
                                                        dist - DistLstTSEltRibbon) / dt) ** 0.125 * dist ** (5 / 8)


# ----------------------------------------------------------------------------------------------------------------------

def f(K, Cb, C1):
    return 1 / (3 * C1) * (
        1 - K ** 3 - 3 * Cb * (1 - K ** 2) / 2 + 3 * Cb ** 2 * (1 - K) - 3 * Cb ** 3 * np.log((Cb + 1) / (Cb + K)))


# ----------------------------------------------------------------------------------------------------------------------

def TipAsym_Universal_delt_Res(dist, *args):
    """More precise function to be minimized to find root for universal Tip assymptote (see Donstov and Pierce)"""

    (wEltRibbon, Kprime, Eprime, muPrime, Cbar, DistLstTSEltRibbon, dt) = args

    Vel = (dist - DistLstTSEltRibbon) / dt
    Kh = Kprime * dist ** 0.5 / (Eprime * wEltRibbon)
    Ch = 2 * Cbar * dist ** 0.5 / (Vel ** 0.5 * wEltRibbon)
    sh = muPrime * Vel * dist ** 2 / (Eprime * wEltRibbon ** 3)

    g0 = f(Kh, 0.9911799823 * Ch, 10.392304845)
    delt = 10.392304845 * (1 + 0.9911799823 * Ch) * g0

    C1 = 4 * (1 - 2 * delt) / (delt * (1 - delt)) * np.tan(math.pi * delt)
    C2 = 16 * (1 - 3 * delt) / (3 * delt * (2 - 3 * delt)) * np.tan(3 * math.pi * delt / 2)
    b = C2 / C1

    return sh - f(Kh, Ch * b, C1)


# ----------------------------------------------------------------------------------------------------------------------

def TipAsym_Universal_zero_Res(dist, *args):
    """Function to be minimized to find root for universal Tip assymptote (see Donstov and Pierce 2017)"""
    (wEltRibbon, Kprime, Eprime, muPrime, Cbar, DistLstTSEltRibbon, dt) = args

    Vel = (dist - DistLstTSEltRibbon) / dt
    Kh = Kprime * dist ** 0.5 / (Eprime * wEltRibbon)
    Ch = 2 * Cbar * dist ** 0.5 / (Vel ** 0.5 * wEltRibbon)
    g0 = f(Kh, 0.9911799823 * Ch, 6 * 3 ** 0.5)
    sh = muPrime * Vel * dist ** 2 / (Eprime * wEltRibbon ** 3)

    return sh - g0


# -----------------------------------------------------------------------------------------------------------------------

def TipAsym_MKTransition_Res(dist, *args):
    """Residual function for viscocity to toughness regime with transition, without leak off"""

    (wEltRibbon, Kprime, Eprime, muPrime, Cbar, DistLstTSEltRibbon, dt) = args
    return wEltRibbon - (1 + 18 * 3 ** 0.5 * Eprime ** 2 * (
        dist - DistLstTSEltRibbon) / dt * muPrime * dist ** 0.5 / Kprime ** 3) ** (
                        1 / 3) * Kprime / Eprime * dist ** 0.5


# ----------------------------------------------------------------------------------------------------------------------

def TipAsym_variable_Toughness_Res(dist, *args):

    (wEltRibbon, Eprime, Kprime_func, alpha, zero_vertex, center_coord) = args

    if zero_vertex == 0:

        x = center_coord[0] + dist * np.cos(alpha)
        y = center_coord[1] + dist * np.sin(alpha)

    elif zero_vertex == 1:

        x = center_coord[0] - dist * np.cos(alpha)
        y = center_coord[1] + dist * np.sin(alpha)

    elif zero_vertex == 2:

        x = center_coord[0] - dist * np.cos(alpha)
        y = center_coord[1] - dist * np.sin(alpha)

    elif zero_vertex == 3:

        x = center_coord[0] + dist * np.cos(alpha)
        y = center_coord[1] - dist * np.sin(alpha)


    return dist - wEltRibbon ** 2 * (Eprime / Kprime_func(x,y)) ** 2

def FindBracket_dist(w, EltRibbon, Kprime, Eprime, muPrime, Cprime, DistLstTS, dt, ResFunc):
    """ 
    Find the valid bracket for the root evaluation function. Also returns list of ribbon cells that are not
    propagating
    """

    stagnant = np.where(
        Kprime * (-DistLstTS[EltRibbon]) ** 0.5 / (Eprime * w[EltRibbon]) > 1)  # propagation condition
    moving = np.arange(EltRibbon.shape[0])[~np.in1d(EltRibbon, EltRibbon[stagnant])]

    a = -DistLstTS[EltRibbon[moving]] * (1 + 1e5 * np.finfo(float).eps)
    b = 10 * (w[EltRibbon[moving]] / (Kprime[moving] / Eprime)) ** 2

    for i in range(0, len(moving)):

        TipAsmptargs = (w[EltRibbon[moving[i]]], Kprime[moving[i]], Eprime, muPrime[EltRibbon[moving[i]]],
                        Cprime[EltRibbon[moving[i]]], -DistLstTS[EltRibbon[moving[i]]], dt)
        Res_a = ResFunc(a[i], *TipAsmptargs)
        Res_b = ResFunc(b[i], *TipAsmptargs)

        cnt = 0
        mid = b[i]
        while Res_a * Res_b > 0:
            mid = (a[i] + 2 * mid) / 3  # weighted
            Res_a = ResFunc(mid, *TipAsmptargs)
            a[i] = mid
            cnt += 1
            if cnt >= 30:  # Should assume not propagating. not set to check how frequently it happens.
                raise SystemExit('Tip Inversion: front distance bracket cannot be found')

    return (moving, a, b)


# ----------------------------------------------------------------------------------------------------------------------

def TipAsymInversion(w, frac, matProp, simParmtrs, dt=None, Kprime_k=None):
    """ 
    Evaluate distance from the front using tip assymptotics of the given regime, given the fracture width in the ribbon
    cells.
    Arguments:
        w (ndarray-float):                      fracture width
        frac (Fracture object):                 current fracture object
        matProp (MaterialProperties object):    Material properties
        simParmtrs (SimulationParameters object): Simulation parameters
        dt (float):                             time step
        Kprime_k (ndarray-float):               Kprime for current iteration of toughness loop. if not given, the Kprime
                                                from the given material properties object will be used for calculation.
    Returns:
        ndarray-float:                          distance (unsigned) from the front for the ribbon cells.
    """

    if not Kprime_k == None:
        Kprime = Kprime_k
    else:
        Kprime = matProp.Kprime

    if simParmtrs.tipAsymptote == 'U':
        ResFunc = TipAsym_Universal_zero_Res
    # ResFunc = TipAsym_Universal_delt_Res
    elif simParmtrs.tipAsymptote == 'Kt':
        return 0  # todo: to be implementd
    elif simParmtrs.tipAsymptote == 'M':
        ResFunc = TipAsym_viscStor_Res
    elif simParmtrs.tipAsymptote == 'Mt':
        ResFunc = TipAsym_viscLeakOff_Res
    elif simParmtrs.tipAsymptote == 'MK':
        ResFunc = TipAsym_MKTransition_Res
    elif simParmtrs.tipAsymptote == 'K':
        return w[frac.EltRibbon] ** 2 * (matProp.Eprime / Kprime) ** 2

    (moving, a, b) = FindBracket_dist(w, frac.EltRibbon, Kprime, matProp.Eprime, frac.muPrime, matProp.Cprime,
                                      frac.sgndDist, dt, ResFunc)
    dist = -frac.sgndDist[frac.EltRibbon]
    for i in range(0, len(moving)):
        # todo: need to use the properties class
        TipAsmptargs = (w[frac.EltRibbon[moving[i]]], Kprime[moving[i]], matProp.Eprime,
                        frac.muPrime[frac.EltRibbon[moving[i]]], matProp.Cprime[frac.EltRibbon[moving[i]]],
                        -frac.sgndDist[frac.EltRibbon[moving[i]]], dt)
        try:
            dist[moving[i]] = brentq(ResFunc, a[i], b[i], TipAsmptargs)
        except RuntimeError:
            dist[moving[i]] = np.nan

    return dist


# -----------------------------------------------------------------------------------------------------------------------

def StressIntensityFactor(w, lvlSetData, EltTip, EltRibbon, stagnant, mesh, Eprime):
    """ 
    This function evaluate the stress intensity factor. See Donstov & Pierce Comput. Methods Appl. Mech. Engrn. 2017
    
    Arguments:
        w (ndarray-float):              fracture width
        lvlSetData (ndarray-float):     the level set values, i.e. distance from the fracture front
        EltTip (ndarray-int):           tip elements
        EltRibbon (ndarray-int):        ribbon elements
        stagnant (ndarray-boolean):     the stagnant tip cells
        mesh (CartesianMesh object):    mesh
        Eprime (float):                 the plain strain modulus
        
    Returns:
        ndarray-float:                  the stress intensity factor of the stagnant cells. Zero is returned for the 
                                        tip cells that are moving.
    """
    KIPrime = np.zeros((EltTip.size,), float)
    for i in range(0, len(EltTip)):
        if stagnant[i]:
            neighbors = mesh.NeiElements[EltTip[i]]
            enclosing = np.append(neighbors, np.asarray(
                [neighbors[2] - 1, neighbors[2] + 1, neighbors[3] - 1, neighbors[3] + 1]))  # eight enclosing cells

            InRibbon = np.asarray([], int)  # find neighbors in Ribbon cells
            for e in range(8):
                found = np.where(EltRibbon == enclosing[e])[0]
                if found.size > 0:
                    InRibbon = np.append(InRibbon, EltRibbon[found[0]])

            if InRibbon.size == 1:
                KIPrime[i] = w[InRibbon[0]] * Eprime / (-lvlSetData[InRibbon[0]]) ** 0.5
            elif InRibbon.size > 1:  # evaluate using least squares method
                KIPrime[i] = Eprime * (w[InRibbon[0]] * (-lvlSetData[InRibbon[0]]) ** 0.5 + w[InRibbon[1]] * (
                    -lvlSetData[InRibbon[1]]) ** 0.5) / (-lvlSetData[InRibbon[0]] - lvlSetData[InRibbon[1]])
            else:  # ribbon cells not found in enclosure, evaluating with the closest ribbon cell
                RibbonCellsDist = ((mesh.CenterCoor[EltRibbon, 0] - mesh.CenterCoor[EltTip[i], 0]) ** 2 + (
                    mesh.CenterCoor[EltRibbon, 1] - mesh.CenterCoor[EltTip[i], 1]) ** 2) ** 0.5
                closest = EltRibbon[np.argmin(RibbonCellsDist)]
                KIPrime[i] = w[closest] * Eprime / (-lvlSetData[closest]) ** 0.5

    return KIPrime

def TipAsymInversion_hetrogenous_toughness(w, frac, mat_prop, level_set):

    zero_vrtx = find_zero_vertex(frac.EltRibbon, level_set, frac.mesh)
    dist = -level_set
    alpha = np.zeros((frac.EltRibbon.size,), dtype=np.float64)

    for i in range(0, len(frac.EltRibbon)):
        if zero_vrtx[i]==0:
            # north-east direction of propagation
            alpha[i] = np.arccos((dist[frac.EltRibbon[i]] - dist[frac.mesh.NeiElements[frac.EltRibbon[i], 1]]) / frac.mesh.hx)

        elif zero_vrtx[i]==1:
            # north-west direction of propagation
            alpha[i] = np.arccos((dist[frac.EltRibbon[i]] - dist[frac.mesh.NeiElements[frac.EltRibbon[i], 0]]) / frac.mesh.hx)

        elif zero_vrtx[i]==2:
            # south-west direction of propagation
            alpha[i] = np.arccos((dist[frac.EltRibbon[i]] - dist[frac.mesh.NeiElements[frac.EltRibbon[i], 0]]) / frac.mesh.hx)

        elif zero_vrtx[i]==3:
            # south-east direction of propagation
            alpha[i] = np.arccos((dist[frac.EltRibbon[i]] - dist[frac.mesh.NeiElements[frac.EltRibbon[i], 1]]) / frac.mesh.hx)

        warnings.filterwarnings("ignore")
        if abs(dist[frac.mesh.NeiElements[frac.EltRibbon[i], 0]] / dist[frac.mesh.NeiElements[frac.EltRibbon[i], 1]] - 1) < 1e-7:
            # if the angle is 90 degrees
            alpha[i] = np.pi / 2
        if abs(dist[frac.mesh.NeiElements[frac.EltRibbon[i], 2]] / dist[frac.mesh.NeiElements[frac.EltRibbon[i], 3]] - 1) < 1e-7:
            # if the angle is 0 degrees
            alpha[i] = 0

    sol = np.zeros((len(frac.EltRibbon),),dtype=np.float64)
    for i in range(0, len(frac.EltRibbon)):

        TipAsmptargs = (w[frac.EltRibbon[i]], mat_prop.Eprime, mat_prop.KprimeFunc, alpha[i], zero_vrtx[i],
               frac.mesh.CenterCoor[frac.EltRibbon[i]])
        residual_zero = TipAsym_variable_Toughness_Res(0, *TipAsmptargs)

        sample_lngths = np.linspace(4*(frac.mesh.hx**2 + frac.mesh.hy**2)**0.5 / 16,4*(frac.mesh.hx**2 + frac.mesh.hy**2)**0.5,16)
        cnt = 0
        res_prdct = 0
        while res_prdct >= 0 and cnt < 16:
            res_prdct = residual_zero * TipAsym_variable_Toughness_Res(sample_lngths[cnt], *TipAsmptargs)
            cnt += 1

        if cnt == 16:# and res_prdct >= 0:
            sol[i] = np.nan
            return sol
        else:
            upper_bracket = sample_lngths[cnt-1]

        try:
            sol[i] = brentq(TipAsym_variable_Toughness_Res, 0, upper_bracket, TipAsmptargs)
        except RuntimeError:
            sol[i] = np.nan

    return sol-sol*1e-10

#-----------------------------------------------------------------------------------------------------------------------
def find_zero_vertex(Elts, level_set, mesh):

    zero_vertex = np.zeros((len(Elts),),dtype=int)
    for i in range(0, len(Elts)):
        neighbors = mesh.NeiElements[Elts]

        if level_set[neighbors[i, 0]] <= level_set[neighbors[i, 1]] and level_set[neighbors[i, 2]] <= level_set[
                                                                                                neighbors[i, 3]]:
            zero_vertex[i] = 0
        elif level_set[neighbors[i, 0]] > level_set[neighbors[i, 1]] and level_set[neighbors[i, 2]] <= level_set[
                                                                                                neighbors[i, 3]]:
            zero_vertex[i] = 1
        elif level_set[neighbors[i, 0]] > level_set[neighbors[i, 1]] and level_set[neighbors[i, 2]] > level_set[
                                                                                                neighbors[i, 3]]:
            zero_vertex[i] = 2
        elif level_set[neighbors[i, 0]] <= level_set[neighbors[i, 1]] and level_set[neighbors[i, 2]] > level_set[
                                                                                                neighbors[i, 3]]:
            zero_vertex[i] = 3

    return zero_vertex