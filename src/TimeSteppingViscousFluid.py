#
# This file is part of PyFrac.
#
# Created by Brice Lecampion on 03.04.17.
# Copyright (c) ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory, 2016-2017.  All rights reserved.
# See the LICENSE.TXT file for more details. 
#

from src.VolIntegral import *
from src.Utility import *
from src.TipInversion import *
from src.ElastoHydrodynamicSolver import *
from src.LevelSet import *
from src.HFAnalyticalSolutions import *
from src.TimeSteppingMechLoading import *
from src.TimeSteppingVolumeControl import *
import copy
import warnings


def attempt_time_step_viscousFluid(Frac, C, Material_properties, Fluid_properties, Simulation_Parameters, Injection_Parameters,
                      TimeStep):
    """ Propagate fracture one time step. The function injects fluid into the fracture, first by keeping the same
    footprint. This gives the first trial value of the width. The ElastoHydronamic system is then solved iteratively
    until convergence is achieved.
    
    Arguments:
        Frac (Fracture object):                             fracture object from the last time step 
        C (ndarray-float):                                  the elasticity matrix 
        Material_properties (MaterialProperties object):    material properties
        Fluid_properties (FluidProperties object):          fluid properties 
        Simulation_Parameters (SimulationParameters object): simulation parameters
        Injection_Parameters (InjectionProperties object):  injection properties
        TimeStep (float):                                   time step 
    
    Return:
        int:   possible values:
                                    0       -- not propagated
                                    1       -- iteration successful
                                    2       -- evaluated level set is not valid
                                    3       -- front is not tracked correctly
                                    4       -- evaluated tip volume is not valid
                                    5       -- solution of elastohydrodynamic solver is not valid
                                    6       -- did not converge after max iterations
                                    7       -- tip inversion not successful
                                    8       -- Ribbon element not found in the enclosure of a tip cell
                                    9       -- Filling fraction not correct
                                    10      -- Toughness iteration did not converge
                                    
        Fracture object:            fracture after advancing time step. 
    """

    exitstatus = 0  # exit code to be returned

    # index of current time in the time series (first row) of the injection rate array
    indxCurTime = max(np.where(Frac.time >= Injection_Parameters.injectionRate[0, :])[0])
    CurrentRate = Injection_Parameters.injectionRate[1, indxCurTime]  # current injection rate

    Qin = np.zeros((Frac.mesh.NumberOfElts), float)
    Qin[Injection_Parameters.source_location] = CurrentRate # current injection over the domain

    # todo : write log file
    # f = open('log', 'a')

    print('Solving ElastoHydrodynamic equations with same footprint...')
    # width by injecting the fracture with the same foot print (balloon like inflation)
    exitstatus, w_k = injection_same_footprint(Frac,
                                               C,
                                               TimeStep,
                                               Qin,
                                               Material_properties,
                                               Fluid_properties,
                                               Simulation_Parameters)

    if exitstatus != 1:
        # failed
        return exitstatus, None


    print('Starting Fracture Front loop...')

    norm = 10.
    k = 0
    Fr_k = Frac

    # Fracture front loop to find the correct front location
    while norm > Simulation_Parameters.tolFractFront:
        k = k + 1
        print('\nIteration ' + repr(k))
        Fr_kminus1 = copy.deepcopy(Fr_k)

        # find the new footprint and solve the elastohydrodynamic equations to to get the new fracture
        (exitstatus, Fr_k) = injection_extended_footprint(w_k,
                                                          Frac,
                                                          C,
                                                          TimeStep,
                                                          Qin,
                                                          Material_properties,
                                                          Fluid_properties,
                                                          Simulation_Parameters)
        if exitstatus != 1:
            return exitstatus, None

        # the new fracture width (notably the new width in the ribbon cells).
        w_k = np.copy(Fr_k.w)

        # norm is evaluated by dividing the difference in the area of the tip cells between two successive iterations
        # with the number of tip cells.
        norm = abs((sum(Fr_k.FillF) - sum(Fr_kminus1.FillF)) / len(Fr_k.FillF))
        print('Norm of subsequent filling fraction estimates = ' + repr(norm))

        if k == Simulation_Parameters.maxFrontItr:
            exitstatus = 6
            return exitstatus, None

    return exitstatus, Fr_k


# ----------------------------------------------------------------------------------------------------------------------

def injection_same_footprint(Fr_lstTmStp, C, timeStep, Qin, mat_properties, Fluid_properties, Simulation_Parameters):
    """
    This function solves the ElastoHydrodynamic equations to get the fracture width. The fracture footprint is taken
    to be the same as in the fracture from the last time step.
    Arguments:
        Fr_lstTmStp (Fracture object):                      fracture object from the last time step 
        C (ndarray-float):                                  the elasticity matrix 
        timeStep (float):                                   time step 
        Qin (ndarray-float):                                current injection rate
        mat_properties (MaterialProperties object):         material properties
        Fluid_properties (FluidProperties object):          fluid properties 
        Simulation_Parameters (SimulationParameters object): simulation parameters
        
    Returns:
        int:            exit status
        ndarray-float:  width of the fracture after injection with the same footprint
    
    """
    C_EltTip = C[np.ix_(Fr_lstTmStp.EltTip, Fr_lstTmStp.EltTip)]  # keeping the tip element entries to restore current
    #  tip correction. This is done to avoid copying the full elasticity matrix.

    # filling fraction correction for element in the tip region
    for e in range(0, len(Fr_lstTmStp.EltTip)):
        r = Fr_lstTmStp.FillF[e] - .25
        if r < 0.1:
            r = 0.1
        ac = (1 - r) / r
        C[Fr_lstTmStp.EltTip[e], Fr_lstTmStp.EltTip[e]] = C[Fr_lstTmStp.EltTip[e], Fr_lstTmStp.EltTip[e]] * (1.
                                                                                                    + ac * np.pi / 4.)

    # average injected fluid over footprint taken as [\delta] W guess for the iterative solver
    delwGuess = timeStep * sum(Qin) / Fr_lstTmStp.EltCrack.size * np.ones((Fr_lstTmStp.EltCrack.size,), float)

    # todo: leak off is assumed zero.
    DLkOff = np.zeros((Fr_lstTmStp.mesh.NumberOfElts,), float)

    # width of the guess. Evaluated to calculate the current velocity at the cell edges
    wguess = np.copy(Fr_lstTmStp.w)
    wguess[Fr_lstTmStp.EltCrack] = wguess[Fr_lstTmStp.EltCrack] + delwGuess

    # velocity at the cell edges evaluated with the guess width. Used as guess values for the implicit velocity solver.
    vk = velocity(wguess,
                  Fr_lstTmStp.EltCrack,
                  Fr_lstTmStp.mesh,
                  Fr_lstTmStp.InCrack,
                  Fr_lstTmStp.muPrime,
                  C,
                  mat_properties.SigmaO)

    argSameFP = (
        Fr_lstTmStp.w,
        Fr_lstTmStp.EltCrack,
        Qin,
        C,
        timeStep,
        Fr_lstTmStp.muPrime,
        Fr_lstTmStp.mesh,
        Fr_lstTmStp.InCrack,
        DLkOff,
        mat_properties.SigmaO,
        Fluid_properties.density,
        Fluid_properties.turbulence,
        mat_properties.grainSize)

    # typical values of the variable. Used to calculate Jacobian (see Piccard_Newton function documentation)
    # todo: guess is taken as typical values. Needs to be reconsidered
    typclValue = delwGuess

    # solving the system
    (sol, vel) = Picard_Newton(Elastohydrodynamic_ResidualFun_sameFP,
                               MakeEquationSystem_viscousFluid_sameFP,
                               delwGuess,
                               typclValue,
                               vk,
                               Simulation_Parameters.toleranceEHL,
                               Simulation_Parameters.maxSolverItr,
                               *argSameFP)

    # getting new width by adding the change in width solution to the width from last time step
    w_k = np.copy(Fr_lstTmStp.w)
    w_k[Fr_lstTmStp.EltCrack] = w_k[Fr_lstTmStp.EltCrack] + sol

    # regain original C (without filling fraction correction)
    C[np.ix_(Fr_lstTmStp.EltTip, Fr_lstTmStp.EltTip)] = C_EltTip


    # check if the width has gone into negative
    # todo: !!! Hack: if the width is negative but greater than some factor times the mean width, it is ignored. This
    #  usually happens when high stress is applied forcing small widths. This will not effect the results as its done
    # in the ballooning of the fracture to get the guess width for the next iteration.
    smallNgtvWTip = np.where(np.logical_and(w_k < 0, w_k > -1 * np.mean(w_k)))
    if np.asarray(smallNgtvWTip).size > 0:
        # warnings.warn("Small negative volume integral(s) received, ignoring "+repr(wTip[smallngtvwTip])+' ...')
        w_k[smallNgtvWTip] = 0.01*abs(w_k[smallNgtvWTip])


    # check if the solution is valid
    if np.isnan(w_k).any() or (w_k < 0).any():
        exitstatus = 5
        return exitstatus, None
    else:
        exitstatus = 1
        return exitstatus, w_k


# -----------------------------------------------------------------------------------------------------------------------

def injection_extended_footprint(w_k, Fr_lstTmStp, C, timeStep, Qin, Material_properties, Fluid_properties,
                                 sim_parameters):
    """
    This function takes the fracture width from the last iteration of the fracture front loop, calculates the level set
    (fracture front position) by inverting the tip asymptote and then solves the ElastoHydrodynamic equations to obtain
    the new fracture width.
     
    Arguments:
        w_k (ndarray-float);                                fracture width from the last iteration
        Fr_lstTmStp (Fracture object):                      fracture object from the last time step 
        C (ndarray-float):                                  the elasticity matrix 
        timeStep (float):                                   time step 
        Qin (ndarray-float):                                current injection rate
        Material_properties (MaterialProperties object):    material properties
        Fluid_properties (FluidProperties object):          fluid properties 
        sim_Parameters (SimulationParameters object):       simulation parameters
    
    Returns:
        int:   possible values:
                                    0       -- not propagated
                                    1       -- iteration successful
                                    2       -- evaluated level set is not valid
                                    3       -- front is not tracked correctly
                                    4       -- evaluated tip volume is not valid
                                    5       -- solution of elastohydrodynamic solver is not valid
                                    6       -- did not converge after max iterations
                                    7       -- tip inversion not successful
                                    8       -- Ribbon element not found in the enclosure of a tip cell
                                    9       -- Filling fraction not correct
                                    10      -- Toughness iteration did not converge

        Fracture object:            fracture after advancing time step. 
    """

    itr = 0
    sgndDist_k = np.copy(Fr_lstTmStp.sgndDist)

    # toughness iteration loop
    while itr < sim_parameters.maxToughnessItr:

        sgndDist_km1 = np.copy(sgndDist_k)
        l_m1 = sgndDist_km1[Fr_lstTmStp.EltRibbon]

        #todo: Only done for anistropic. Has to be done for heterogenous toughness
        if Material_properties.anisotropic:
            Kprime_k = toughness_at_tip_CellCenter(Fr_lstTmStp.EltRibbon,
                                                   Fr_lstTmStp.mesh,
                                                   Material_properties,
                                                   sgndDist_k)
        else:
            Kprime_k = None

        # Initialization of the signed distance in the ribbon element - by inverting the tip asymptotics
        sgndDist_k = 1e10 * np.ones((Fr_lstTmStp.mesh.NumberOfElts,), float)  # Initializing the cells with extremely
                                                                        # large float value. (algorithm requires inf)

        sgndDist_k[Fr_lstTmStp.EltRibbon] = - TipAsymInversion(w_k,
                                                               Fr_lstTmStp,
                                                               Material_properties,
                                                               sim_parameters,
                                                               timeStep,
                                                               Kprime_k=Kprime_k)


        # if tip inversion returns nan
        if np.isnan(sgndDist_k[Fr_lstTmStp.EltRibbon]).any():
            exitstatus = 7
            return exitstatus, None

        # region expected to have the front after propagation. The signed distance of the cells only in this region will
        # evaluated with the fast marching method to avoid unnecessary computation cost
        front_region = np.where(abs(Fr_lstTmStp.sgndDist) < 2 * (Fr_lstTmStp.mesh.hx**2 + Fr_lstTmStp.mesh.hy**2)**0.5)[0]
        # the search region outwards from the front position at last time step
        pstv_region = np.where(Fr_lstTmStp.sgndDist[front_region] >= -(Fr_lstTmStp.mesh.hx**2 +
                                                                  Fr_lstTmStp.mesh.hy**2)**0.5)[0]
        # the search region inwards from the front position at last time step
        ngtv_region = np.where(Fr_lstTmStp.sgndDist[front_region] < 0)[0]

        # SOLVE EIKONAL eq via Fast Marching Method starting to get the distance from tip for each cell.
        SolveFMM(sgndDist_k,
                 Fr_lstTmStp.EltRibbon,
                 Fr_lstTmStp.EltChannel,
                 Fr_lstTmStp.mesh,
                 front_region[pstv_region],
                 front_region[ngtv_region])

        # # if some elements remain unevaluated by fast marching method. It happens with unrealistic fracture geometry.
        # # todo: not satisfied with why this happens. need re-examining
        # if max(sgndDist_k) == 1e10:
        #     exitstatus = 2
        #     return exitstatus, None

        norm = np.linalg.norm(1 - abs(l_m1/sgndDist_k[Fr_lstTmStp.EltRibbon]))
        if norm < sim_parameters.toleranceToughness:
            print("toughness iteration converged after " + repr(itr-1) + " iterations; exiting norm " +
                  repr(norm))
            break

        # do it only once if KprimeFunc
        if Material_properties.KprimeFunc is None:
            break

        print("iterating on toughness...")
        itr += 1

    if itr == sim_parameters.maxToughnessItr:
        exitstatus = 10
        return exitstatus, None

    # gets the new tip elements, along with the length and angle of the perpendiculars drawn on front (also containing
    # the elements which are fully filled after the front is moved outward)
    (EltsTipNew, l_k, alpha_k, CellStatus) = reconstruct_front(sgndDist_k,
                                                                Fr_lstTmStp.EltChannel,
                                                                Fr_lstTmStp.mesh)

    # If the angle and length of the perpendicular are not correct
    nan = np.logical_or(np.isnan(alpha_k), np.isnan(l_k))
    if nan.any() or (l_k < 0).any() or (alpha_k < 0).any() or (alpha_k > np.pi / 2).any():
        exitstatus = 3
        return exitstatus, None

    # check if any of the tip cells has a neighbor outside the grid, i.e. fracture has reached the end of the grid.
    tipNeighb = Fr_lstTmStp.mesh.NeiElements[EltsTipNew, :]
    for i in range(0, len(EltsTipNew)):
        if (np.where(tipNeighb[i, :] == EltsTipNew[i])[0]).size > 0:
            Fr_lstTmStp.plot_fracture('complete', 'footPrint')
            raise SystemExit('Reached end of the grid. exiting....')

    # generate the InCrack array for the current front position
    InCrack_k = np.zeros((Fr_lstTmStp.mesh.NumberOfElts,), dtype=np.int8)
    InCrack_k[Fr_lstTmStp.EltChannel] = 1
    InCrack_k[EltsTipNew] = 1

    # the velocity of the front for the current front position
    # todo: not accurate on the first iteration. needed to be checked
    Vel_k = -(sgndDist_k[EltsTipNew] - Fr_lstTmStp.sgndDist[EltsTipNew]) / timeStep


    # Calculate filling fraction of the tip cells for the current fracture position
    FillFrac_k = VolumeIntegral(EltsTipNew,
                                alpha_k,
                                l_k,
                                Fr_lstTmStp.mesh,
                                'A',
                                Material_properties,
                                Fr_lstTmStp.muPrime,
                                Vel_k) / Fr_lstTmStp.mesh.EltArea

    # todo !!! Hack: This check rounds the filling fraction to 1 if it is not bigger than 1 + 1e-6 (up to 6 figures)
    FillFrac_k[np.logical_and(FillFrac_k > 1.0, FillFrac_k < 1 + 1e-6)] = 1.0

    # if filling fraction is below zero or above 1+1e-6
    if (FillFrac_k > 1.0).any() or (FillFrac_k < 0.0 - np.finfo(float).eps).any():
        exitstatus = 9
        return exitstatus, None

    # todo: some of the list are redundant to calculate on each iteration
    # Evaluate the element lists for the trial fracture front
    (EltChannel_k,
     EltTip_k,
     EltCrack_k,
     EltRibbon_k,
     zrVertx_k,
     CellStatus_k) = UpdateLists(Fr_lstTmStp.EltChannel,
                                 EltsTipNew,
                                 FillFrac_k,
                                 sgndDist_k,
                                 Fr_lstTmStp.mesh)

    # EletsTipNew may contain fully filled elements also. Identifying only the partially filled elements
    partlyFilledTip = np.arange(EltsTipNew.shape[0])[np.in1d(EltsTipNew, EltTip_k)]

    print('Solving the EHL system with the new trial footprint')

    # Calculating toughness at tip to be used to calculate the volume integral in the tip cells
    # zrVrtx_newTip = find_zero_vertex(EltsTipNew, sgndDist_k, Fr_lstTmStp.mesh)
    # Kprime_tip = toughness_at_tip_zeroVertex(EltsTipNew,
    #                                        Fr_lstTmStp.mesh,
    #                                        Material_properties,
    #                                        alpha_k,
    #                                        l_k,
    #                                        zrVrtx_newTip)

    # stagnant tip cells i.e. the tip cells whose distance from front has not changed.
    stagnant = abs(1 - sgndDist_k[EltsTipNew] / Fr_lstTmStp.sgndDist[EltsTipNew]) < 1e-5
    if stagnant.any():
        # if any tip cell with stagnant front
        # calculate stress intensity factor for stagnant cells
        KIPrime = StressIntensityFactor(w_k,
                                        sgndDist_k,
                                        EltsTipNew,
                                        EltRibbon_k,
                                        stagnant,
                                        Fr_lstTmStp.mesh,
                                        Material_properties.Eprime)

        # todo: Find the right cause of failure
        # if the stress Intensity factor cannot be found. The most common reason is wiggles in the front resulting
        # in isolated tip cells.
        if np.isnan(KIPrime).any():
            exitstatus = 8
            return exitstatus, None

        # Calculate average width in the tip cells by integrating tip asymptote. Width of stagnant cells are calculated
        # using the stress intensity factor (see Dontsov and Peirce, JFM RAPIDS, 2017)
        wTip = VolumeIntegral(EltsTipNew,
                              alpha_k,
                              l_k,
                              Fr_lstTmStp.mesh,
                              sim_parameters.tipAsymptote,
                              Material_properties,
                              Fr_lstTmStp.muPrime,
                              Vel_k,
                              stagnant=stagnant,
                              KIPrime=KIPrime
                              ) / Fr_lstTmStp.mesh.EltArea
    else:
        # Calculate average width in the tip cells by integrating tip asymptote
        wTip = VolumeIntegral(EltsTipNew,
                              alpha_k,
                              l_k,
                              Fr_lstTmStp.mesh,
                              sim_parameters.tipAsymptote,
                              Material_properties,
                              Fr_lstTmStp.muPrime,
                              Vel_k) / Fr_lstTmStp.mesh.EltArea

    # # check if the tip volume has gone into negative
    # smallNgtvWTip = np.where(np.logical_and(wTip < 0, wTip > -1e-4 * np.mean(wTip)))
    # if np.asarray(smallNgtvWTip).size > 0:
    #     #                    warnings.warn("Small negative volume integral(s) received, ignoring "+repr(wTip[smallngtvwTip])+' ...')
    #     wTip[smallNgtvWTip] = abs(wTip[smallNgtvWTip])


    if (wTip < 0).any():
        exitstatus = 4
        return exitstatus, None

    guess = np.zeros((Fr_lstTmStp.EltChannel.size + EltsTipNew.size,), float)
    # pguess = Fr_lstTmStp.p[EltsTipNew]

    guess[np.arange(Fr_lstTmStp.EltChannel.size)] = timeStep * sum(Qin) / Fr_lstTmStp.EltCrack.size \
                                                    * np.ones((Fr_lstTmStp.EltCrack.size,), float)
    DLkOff = np.zeros((Fr_lstTmStp.mesh.NumberOfElts,), float)  # leak off set to zero

    # width of guess. Evaluated to calculate the current velocity at the cell edges
    wguess = np.copy(Fr_lstTmStp.w)
    wguess[Fr_lstTmStp.EltChannel] = wguess[Fr_lstTmStp.EltChannel] + guess[np.arange(Fr_lstTmStp.EltChannel.size)]
    wguess[EltsTipNew] = wTip

    # velocity at the cell edges evaluated with the guess width. Used as guess values for the implicit velocity solver.
    vk = velocity(wguess,
                  EltCrack_k,
                  Fr_lstTmStp.mesh,
                  InCrack_k,
                  Fr_lstTmStp.muPrime,
                  C,
                  Material_properties.SigmaO)

    # typical value for pressure
    typValue = np.copy(guess)
    typValue[Fr_lstTmStp.EltChannel.size + np.arange(EltsTipNew.size)] = 1e5

    # todo too many arguments; properties class needs to be utilized
    arg = (
        Fr_lstTmStp.EltChannel,
        EltsTipNew,
        Fr_lstTmStp.w,
        wTip,
        EltCrack_k,
        Fr_lstTmStp.mesh,
        timeStep,
        Qin,
        C,
        Fr_lstTmStp.muPrime,
        Fluid_properties.density,
        InCrack_k,
        DLkOff,
        Material_properties.SigmaO,
        Fluid_properties.turbulence,
        Material_properties.grainSize
        )

    # sloving the system of equations for the change in width in the channel elements and pressure in the tip elements
    (sol, vel) = Picard_Newton(Elastohydrodynamic_ResidualFun_ExtendedFP,
                               MakeEquationSystem_viscousFluid_extendedFP,
                               guess,
                               typValue,
                               vk,
                               sim_parameters.toleranceEHL,
                               sim_parameters.maxSolverItr,
                               *arg)

    # the fracture to be returned for k plus 1 iteration
    Fr_kplus1 = copy.deepcopy(Fr_lstTmStp)

    Fr_kplus1.time += timeStep

    Fr_kplus1.w[Fr_lstTmStp.EltChannel] += sol[np.arange(Fr_lstTmStp.EltChannel.size)]
    Fr_kplus1.w[EltsTipNew] = wTip

    # check if the new width is valid
    if np.isnan(Fr_kplus1.w).any()  :
        exitstatus = 5
        return exitstatus, None

    if (Fr_kplus1.w < 0).any():  #todo: clean this up as it might blow up !    -> we need a linear solver with constraint to handle pinch point properly.
        print(repr(np.where((Fr_kplus1.w < 0))))
        print(repr(Fr_kplus1.w[np.where((Fr_kplus1.w < 0))[0]]))
#        exitstatus = 5
#        return exitstatus, None

    Fr_kplus1.FillF = FillFrac_k[partlyFilledTip]
    Fr_kplus1.EltChannel = EltChannel_k
    Fr_kplus1.EltTip = EltTip_k
    Fr_kplus1.EltCrack = EltCrack_k
    Fr_kplus1.EltRibbon = EltRibbon_k
    Fr_kplus1.ZeroVertex = zrVertx_k

    # pressure evaluated by dot product of width and elasticity matrix
    Fr_kplus1.p[Fr_kplus1.EltCrack] = np.dot(C[np.ix_(Fr_kplus1.EltCrack, Fr_kplus1.EltCrack)],
                                             Fr_kplus1.w[Fr_kplus1.EltCrack])
    Fr_kplus1.sgndDist = sgndDist_k

    Fr_kplus1.alpha = alpha_k[partlyFilledTip]
    Fr_kplus1.l = l_k[partlyFilledTip]
    Fr_kplus1.v = Vel_k[partlyFilledTip]

    Fr_kplus1.InCrack = InCrack_k

    Fr_kplus1.process_fracture_front()
    Fr_kplus1.FractureVolume = np.sum(Fr_kplus1.w) * (Fr_kplus1.mesh.EltArea)

    # # check if the tip has laminar flow, to be consistent with tip asymptote.
    # ReNumb, check = turbulence_check_tip(vel, Fr_kplus1, Fluid_properties, return_ReyNumb=True)
    # # plot Reynold's number
    # plot_Reynolds_number(Fr_kplus1, ReNumb, 1)

    exitstatus = 1
    return exitstatus, Fr_kplus1

#-----------------------------------------------------------------------------------------------------------------------

def turbulence_check_tip(vel, Fr, fluid, return_ReyNumb=False):
    """
    This function calculate the Reynolds number at the cell edges and check if any to the edge between the ribbon cells
    and the tip cells are turbulent (i.e. the Reynolds number is greater than 2100).
    
    Arguments:
        vel (ndarray-float):                    the array giving velocity of each edge of the cells in domain 
        Fr (Fracture object):                   the fracture object to be checked
        fluid (FluidProperties object):         fluid properties object 
        return_ReyNumb (boolean, default False): if true, Reynolds number at all cell edges will be returned 
    
    Returns:
        ndarray-float:      Reynolds number of all the cells in the domain; row-wise in the following order : 0--left,
                            1--right, 2--bottom, 3--top
        boolean             true if any of the edge between the ribbon and tip cells is turbulent (i.e. Reynolds number
                            is more than 2100)
    """
    # width at the adges by averaging
    wLftEdge = (Fr.w[Fr.EltRibbon] + Fr.w[Fr.mesh.NeiElements[Fr.EltRibbon, 0]]) / 2
    wRgtEdge = (Fr.w[Fr.EltRibbon] + Fr.w[Fr.mesh.NeiElements[Fr.EltRibbon, 1]]) / 2
    wBtmEdge = (Fr.w[Fr.EltRibbon] + Fr.w[Fr.mesh.NeiElements[Fr.EltRibbon, 2]]) / 2
    wTopEdge = (Fr.w[Fr.EltRibbon] + Fr.w[Fr.mesh.NeiElements[Fr.EltRibbon, 3]]) / 2

    Re = np.zeros((4, Fr.EltRibbon.size, ), dtype=np.float64)
    Re[0, :] = 4 / 3 * fluid.density * wLftEdge * vel[0, Fr.EltRibbon] / fluid.viscosity
    Re[1, :] = 4 / 3 * fluid.density * wRgtEdge * vel[1, Fr.EltRibbon] / fluid.viscosity
    Re[2, :] = 4 / 3 * fluid.density * wBtmEdge * vel[2, Fr.EltRibbon] / fluid.viscosity
    Re[3, :] = 4 / 3 * fluid.density * wTopEdge * vel[3, Fr.EltRibbon] / fluid.viscosity

    ReNum_Ribbon = []
    # adding Reynolds number of the edges between the ribbon and tip cells to a list
    for i in range(0,Fr.EltRibbon.size):
        for j in range(0,4):
            # if the current neighbor (j) of the ribbon cells is in the tip elements list
            if np.where(Fr.mesh.NeiElements[Fr.EltRibbon[i], j] == Fr.EltTip)[0].size>0:
                ReNum_Ribbon = np.append(ReNum_Ribbon, Re[j, i])

    if return_ReyNumb:
        wLftEdge = (Fr.w[Fr.EltCrack] + Fr.w[Fr.mesh.NeiElements[Fr.EltCrack, 0]]) / 2
        wRgtEdge = (Fr.w[Fr.EltCrack] + Fr.w[Fr.mesh.NeiElements[Fr.EltCrack, 1]]) / 2
        wBtmEdge = (Fr.w[Fr.EltCrack] + Fr.w[Fr.mesh.NeiElements[Fr.EltCrack, 2]]) / 2
        wTopEdge = (Fr.w[Fr.EltCrack] + Fr.w[Fr.mesh.NeiElements[Fr.EltCrack, 3]]) / 2

        Re = np.zeros((4, Fr.mesh.NumberOfElts,), dtype=np.float64)
        Re[0, Fr.EltCrack] = 4 / 3 * fluid.density * wLftEdge * vel[0, Fr.EltCrack] / fluid.viscosity
        Re[1, Fr.EltCrack] = 4 / 3 * fluid.density * wRgtEdge * vel[1, Fr.EltCrack] / fluid.viscosity
        Re[2, Fr.EltCrack] = 4 / 3 * fluid.density * wBtmEdge * vel[2, Fr.EltCrack] / fluid.viscosity
        Re[3, Fr.EltCrack] = 4 / 3 * fluid.density * wTopEdge * vel[3, Fr.EltCrack] / fluid.viscosity

        return Re, (ReNum_Ribbon > 2100.).any()
    else:
        return (ReNum_Ribbon > 2100.).any()

#-----------------------------------------------------------------------------------------------------------------------

def toughness_at_tip_CellCenter(ribbon_elts, mesh, mat_prop, sgnd_dist):
    """
    This function gives the scaled toughness(Kprime) at the closest tip point from the cell centers of the ribbon cells.
    The function is different from the toughness_at_tip as it calculates the closest tip from cell centers and not from
    the zero vertex.
    Arguments:
        ribbon_elts (ndarray-int): list of ribbon elements
        mesh (CartesianMesh object): The cartesian mesh object
        mat_prop (MaterialProperties object):    Material properties:
        sgnd_dist (ndarray-float): level set data

    Returns:
        ndarray-float : Kprime at the closest tip point from the center of the given ribbon cells
    """

    dist = -sgnd_dist
    alpha = np.zeros((ribbon_elts.size,), dtype=np.float64)
    zero_vertex = find_zero_vertex(ribbon_elts, sgnd_dist, mesh)
    neighbors = mesh.NeiElements[ribbon_elts]
    for i in range(0, len(ribbon_elts)):
        if zero_vertex[i]==0:
            # north-east direction of propagation
            alpha[i] = np.arccos((dist[ribbon_elts[i]] - dist[mesh.NeiElements[ribbon_elts[i], 1]]) / mesh.hx)

        elif zero_vertex[i]==1:
            # north-west direction of propagation
            alpha[i] = np.arccos((dist[ribbon_elts[i]] - dist[mesh.NeiElements[ribbon_elts[i], 0]]) / mesh.hx)

        elif zero_vertex[i]==2:
            # south-west direction of propagation
            alpha[i] = np.arccos((dist[ribbon_elts[i]] - dist[mesh.NeiElements[ribbon_elts[i], 0]]) / mesh.hx)

        elif zero_vertex[i]==3:
            # south-east direction of propagation
            alpha[i] = np.arccos((dist[ribbon_elts[i]] - dist[mesh.NeiElements[ribbon_elts[i], 1]]) / mesh.hx)

        warnings.filterwarnings("ignore")
        if abs(dist[mesh.NeiElements[ribbon_elts[i], 0]] / dist[mesh.NeiElements[ribbon_elts[i], 1]] - 1) < 1e-7:
            # if the angle is 90 degrees
            alpha[i] = np.pi / 2
        if abs(dist[mesh.NeiElements[ribbon_elts[i], 2]] / dist[mesh.NeiElements[ribbon_elts[i], 3]] - 1) < 1e-7:
            # if the angle is 0 degrees
            alpha[i] = 0

    if mat_prop.anisotropic:
        return mat_prop.KprimeFunc(alpha)
    else:

        x = np.zeros((len(ribbon_elts),),)
        y = np.zeros((len(ribbon_elts),), )

        # evaluating the closest tip points
        for i in range(0, len(ribbon_elts)):
            if zero_vertex[i]==0:

                x[i] = mesh.CenterCoor[ribbon_elts[i],0] + dist[ribbon_elts[i]] * np.cos(alpha[i])
                y[i] = mesh.CenterCoor[ribbon_elts[i],1] + dist[ribbon_elts[i]] * np.sin(alpha[i])

            elif zero_vertex[i]==1:

                x[i] = mesh.CenterCoor[ribbon_elts[i],0] - dist[ribbon_elts[i]] * np.cos(alpha[i])
                y[i] = mesh.CenterCoor[ribbon_elts[i],1] + dist[ribbon_elts[i]] * np.sin(alpha[i])

            elif zero_vertex[i]==2:

                x[i] = mesh.CenterCoor[ribbon_elts[i],0] - dist[ribbon_elts[i]] * np.cos(alpha[i])
                y[i] = mesh.CenterCoor[ribbon_elts[i],1] - dist[ribbon_elts[i]] * np.sin(alpha[i])

            elif zero_vertex[i]==3:

                x[i] = mesh.CenterCoor[ribbon_elts[i],0] + dist[ribbon_elts[i]] * np.cos(alpha[i])
                y[i] = mesh.CenterCoor[ribbon_elts[i],1] - dist[ribbon_elts[i]] * np.sin(alpha[i])

            if abs(dist[mesh.NeiElements[ribbon_elts[i],0]]/dist[mesh.NeiElements[ribbon_elts[i],1]]-1) < 1e-7:
                if sgnd_dist[neighbors[i,2]] < sgnd_dist[neighbors[i,3]]:
                    x[i] = mesh.CenterCoor[ribbon_elts[i], 0]
                    y[i] = mesh.CenterCoor[ribbon_elts[i], 1] + dist[ribbon_elts[i]]
                elif sgnd_dist[neighbors[i,2]] > sgnd_dist[neighbors[i,3]]:
                    x[i] = mesh.CenterCoor[ribbon_elts[i], 0]
                    y[i] = mesh.CenterCoor[ribbon_elts[i], 1] - dist[ribbon_elts[i]]

        # returning the Kprime according to the given function
        return mat_prop.KprimeFunc(x, y)

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

def toughness_at_tip_zeroVertex(elts, mesh, mat_prop, alpha, l, zero_vrtx):

    if mat_prop.anisotropic:
        return mat_prop.KprimeFunc(alpha)
    else:
        x = np.zeros((len(elts),), )
        y = np.zeros((len(elts),), )
        for i in range(0, len(elts)):
            if zero_vrtx[i] == 0:
                x[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 0], 0] + l[i] * np.cos(alpha[i])
                y[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 0], 1] + l[i] * np.sin(alpha[i])
            elif zero_vrtx[i] == 1:
                x[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 1], 0] - l[i] * np.cos(alpha[i])
                y[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 1], 1] + l[i] * np.sin(alpha[i])
            elif zero_vrtx[i] == 2:
                x[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 2], 0] - l[i] * np.cos(alpha[i])
                y[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 2], 1] - l[i] * np.sin(alpha[i])
            elif zero_vrtx[i] == 3:
                x[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 3], 0] + l[i] * np.cos(alpha[i])
                y[i] = mesh.VertexCoor[mesh.Connectivity[elts[i], 3], 1] - l[i] * np.sin(alpha[i])

        return mat_prop.KprimeFunc(x, y)