#
# This file is part of PyFrac.
#
# Created by Haseeb Zia on 11.07.17.
# Copyright (c) ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory, 2016-2017.  All rights
# reserved. See the LICENSE.TXT file for more details.
#


import copy
import time
from src.TipInversion import *
from src.ElastoHydrodynamicSolver import *
from src.LevelSet import *
from src.VolIntegral import *
from src.anisotropy import projection_from_ribbon, get_toughness_from_cellCenter, get_toughness_from_zeroVertex
from src.Properties import IterationProperties

def attempt_time_step_volumeControl(Frac, C, Material_properties, Simulation_Parameters, Injection_Parameters,
                                    TimeStep, PerfNode=None):
    """ Propagate fracture one time step assuming uniform pressure (inviscid fluid). The function injects fluid into the fracture, first by keeping the same
    footprint. This gives the first trial value of the width. The ElastoHydronamic system is then solved iteratively
    until the final footprint position convergences.

    Arguments:
        Frac (Fracture object):                             fracture object from the last time step
        C (ndarray-float):                                  the elasticity matrix
        Material_properties (MaterialProperties object):    material properties
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

        Fracture object:            fracture after advancing the given time step.
    """
    indxCurTime = max(np.where(Frac.time >= Injection_Parameters.injectionRate[0, :])[0])
    Qin = Injection_Parameters.injectionRate[1, indxCurTime]  # current injection rate

    # todo : write log file
    # f = open('log', 'a')

    if Simulation_Parameters.frontAdvancing == 'explicit':

        # make a new performance collection node to collect data about the explicit time step advancement
        if PerfNode is not None:
            PerfNode_explFront = IterationProperties(itr_type="explicit front")
            PerfNode_explFront.subIterations = [[], [], []]
        else:
            PerfNode_explFront = None

        exitstatus, Fr_k = time_step_explicit_front_volumeControl(Frac,
                                                    C,
                                                    TimeStep,
                                                    Qin,
                                                    Material_properties,
                                                    Simulation_Parameters,
                                                    PerfNode_explFront)

        if PerfNode_explFront is not None:
            PerfNode_explFront.CpuTime_end = time.time()
            PerfNode.iterations += 1
            PerfNode.normList.append(np.nan)
            PerfNode.subIterations[0].append(PerfNode_explFront)
            if exitstatus != 1:
                PerfNode.time = Frac.time + TimeStep
                PerfNode.failure_cause = exitstatus
            else:
                PerfNode.time = Fr_k.time

        return exitstatus, Fr_k

    elif Simulation_Parameters.frontAdvancing == 'semi-implicit':
        if Simulation_Parameters.verbosity > 1:
            print('Advancing front with velocity from last time-step...')

        if PerfNode is not None:
            PerfNode_explFront = IterationProperties(itr_type="explicit front")
            PerfNode_explFront.subIterations = [[], [], []]
        else:
            PerfNode_explFront = None

        exitstatus, Fr_k = time_step_explicit_front_volumeControl(Frac,
                                                                  C,
                                                                  TimeStep,
                                                                  Qin,
                                                                  Material_properties,
                                                                  Simulation_Parameters,
                                                                  PerfNode_explFront)


        if PerfNode_explFront is not None:
            PerfNode_explFront.CpuTime_end = time.time()
            PerfNode.iterations += 1
            PerfNode.normList.append(np.nan)
            PerfNode.subIterations[0].append(PerfNode_explFront)
            if exitstatus != 1:
                PerfNode.time = Frac.time + TimeStep
                PerfNode.failure_cause = exitstatus

        if exitstatus == 1:
            w_k = np.copy(Fr_k.w)

    elif Simulation_Parameters.frontAdvancing == 'implicit':
        if Simulation_Parameters.verbosity > 1:
            print('Solving ElastoHydrodynamic equations with same footprint...')

        if PerfNode is not None:
            PerfNode_sameFP = IterationProperties(itr_type="same footprint injection")
            PerfNode_sameFP.subIterations = []
        else:
            PerfNode_sameFP = None

        # width by injecting the fracture with the same foot print (balloon like inflation)
        exitstatus, w_k = injection_same_footprint_volumeControl(Frac,
                                                                    C,
                                                                    TimeStep,
                                                                    Qin,
                                                                    PerfNode_sameFP)

        if PerfNode_sameFP is not None:
            PerfNode_sameFP.CpuTime_end = time.time()
            PerfNode.iterations += 1
            PerfNode.normList.append(np.nan)
            PerfNode.subIterations[1].append(PerfNode_sameFP)
            if exitstatus != 1:
                PerfNode.time = Frac.time + TimeStep
                PerfNode.failure_cause = exitstatus
    else:
        raise ValueError("Provided front advancing type not supported")

    if exitstatus != 1:
        # failed
        return exitstatus, None


    if Simulation_Parameters.verbosity > 1:
        print('Starting Fracture Front loop...')

    norm = 1e10 # higher than tolerance for first iteration
    k = 0       # zeroth iteration
    Fr_k = Frac

    # Fracture front loop to find the correct front location
    while norm > Simulation_Parameters.tolFractFront:
        k = k + 1
        if Simulation_Parameters.verbosity > 1:
            print('\nIteration ' + repr(k))

        fill_frac_last = np.copy(Fr_k.FillF)

        if PerfNode is not None:
            PerfNode_extendedFP = IterationProperties(itr_type="extended footprint injection")
            PerfNode_extendedFP.subIterations = [[], [], []]
        else:
            PerfNode_extendedFP = None

        # find the new footprint and solve the elastohydrodynamic equations to to get the new fracture
        (exitstatus, Fr_k) = injection_extended_footprint_volumeControl(w_k,
                                                              Frac,
                                                              C,
                                                              TimeStep,
                                                              Qin,
                                                              Material_properties,
                                                              Simulation_Parameters,
                                                              PerfNode_extendedFP)

        if exitstatus == 1:
            # the new fracture width (notably the new width in the ribbon cells).
            w_k = np.copy(Fr_k.w)

            # norm is evaluated by dividing the difference in the area of the tip cells between two successive iterations
            # with the number of tip cells.
            norm = abs((sum(Fr_k.FillF) - sum(fill_frac_last)) / len(Fr_k.FillF))
        else:
            norm = np.nan

        if PerfNode_extendedFP is not None:
            PerfNode_extendedFP.CpuTime_end = time.time()
            PerfNode.iterations += 1
            PerfNode.normList.append(norm)
            PerfNode.subIterations[2].append(PerfNode_extendedFP)
            if exitstatus != 1:
                PerfNode.time = Frac.time + TimeStep
                PerfNode.failure_cause = exitstatus

        if exitstatus != 1:
            return exitstatus, None

        if k == Simulation_Parameters.maxFrontItr:
            exitstatus = 6
            if PerfNode_extendedFP is not None:
                PerfNode.time = Frac.time + TimeStep
                PerfNode.failure_cause = exitstatus
            return exitstatus, None

    if Simulation_Parameters.verbosity > 1:
        print("Fracture front converged after " + repr(k) + " iterations with norm = " + repr(norm))

    if PerfNode is not None:
        PerfNode.time = Fr_k.time

    return exitstatus, Fr_k

#-----------------------------------------------------------------------------------------------------------------------

def injection_same_footprint_volumeControl(Fr_lstTmStp, C, timeStep, Q, performance_node=None):
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

    if performance_node is not None:
        performance_node.iterations += 1
        PerfNode_linSolve = IterationProperties(itr_type="Linear solve iterations")
        PerfNode_linSolve.subIterations = []
    else:
        PerfNode_linSolve = None

    (A, b) = MakeEquationSystem_volumeControl_sameFP(Fr_lstTmStp.w,
                                                     Fr_lstTmStp.EltCrack,
                                                     C,
                                                     timeStep,
                                                     Q,
                                                     Fr_lstTmStp.mesh.EltArea)
    sol = np.linalg.solve(A, b)

    if PerfNode_linSolve is not None:
        PerfNode_linSolve.CpuTime_end = time.time()
        performance_node.subIterations.append(PerfNode_linSolve)

    # getting new width by adding the change in width solution to the width from last time step
    w_k = np.copy(Fr_lstTmStp.w)
    w_k[Fr_lstTmStp.EltCrack] += sol[np.arange(Fr_lstTmStp.EltCrack.size)]


    # regain original C (without filling fraction correction)
    C[np.ix_(Fr_lstTmStp.EltTip, Fr_lstTmStp.EltTip)] = C_EltTip

    # # check if the width has gone into negative
    # # todo: !!! Hack: if the width is negative but greater than some factor times the mean width, it is ignored. This
    # #  usually happens when high stress is applied forcing small widths. This will not effect the results as its done
    # # in the ballooning of the fracture to get the guess width for the next iteration.
    # smallNgtvWTip = np.where(np.logical_and(w_k < 0, w_k > -1 * np.mean(w_k)))
    # if np.asarray(smallNgtvWTip).size > 0:
    #     # warnings.warn("Small negative volume integral(s) received, ignoring "+repr(wTip[smallngtvwTip])+' ...')
    #     w_k[smallNgtvWTip] = 0.01 * abs(w_k[smallNgtvWTip])



    # check if the solution is valid
    if np.isnan(w_k).any():# or (w_k < 0).any():
        exitstatus = 5
        return exitstatus, None
    else:
        exitstatus = 1
        return exitstatus, w_k

#-----------------------------------------------------------------------------------------------------------------------

def injection_extended_footprint_volumeControl(w_k, Fr_lstTmStp, C, timeStep, Qin, Material_properties, sim_parameters,
                                               performance_node=None):
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

        Fracture object:            fracture after advancing time step.
    """

    itr = 1
    sgndDist_k = np.copy(Fr_lstTmStp.sgndDist)
    if not Material_properties.K1cFunc is None:
        alpha_ribbon = projection_from_ribbon(Fr_lstTmStp.EltRibbon,
                                                 Fr_lstTmStp.EltChannel,
                                                 Fr_lstTmStp.mesh,
                                                 sgndDist_k)
        Kprime_k = (32 / math.pi) ** 0.5 * get_toughness_from_cellCenter(alpha_ribbon,
                                                sgndDist_k,
                                                Fr_lstTmStp.EltRibbon,
                                                Material_properties,
                                                Fr_lstTmStp.mesh)
    # Kprime from last iteration; starts with zero
        Kprime_km1 = 0*np.copy(Kprime_k)

    # toughness iteration loop
    while itr < sim_parameters.maxToughnessItr:

        sgndDist_km1 = np.copy(sgndDist_k)

        if not Material_properties.K1cFunc is None:
            alpha_ribbon = projection_from_ribbon(Fr_lstTmStp.EltRibbon,
                                                  Fr_lstTmStp.EltChannel,
                                                  Fr_lstTmStp.mesh,
                                                  sgndDist_k)
            if np.isnan(alpha_ribbon).any():
                exitstatus = 11
                return exitstatus, None
            # under relaxing toughnesss
            Kprime_k = 0.3 * Kprime_k + 0.7 * get_toughness_from_cellCenter(alpha_ribbon,
                                                            sgndDist_k,
                                                            Fr_lstTmStp.EltRibbon,
                                                            Material_properties,
                                                            Fr_lstTmStp.mesh) * (32 / math.pi) ** 0.5
            if np.isnan(Kprime_k).any():
                exitstatus = 11
                return exitstatus, None
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
            # print("The angle is not correct. Trying to use angle from last time step...")
            # sgndDist_k = sgndDist_km1
            # break
            return exitstatus, None

        sgndDist_k[Fr_lstTmStp.EltRibbon] = np.minimum(sgndDist_k[Fr_lstTmStp.EltRibbon],
                                                Fr_lstTmStp.sgndDist[Fr_lstTmStp.EltRibbon])

        # region expected to have the front after propagation. The signed distance of the cells only in this region will
        # be evaluated with the fast marching method to avoid unnecessary computational cost.
        front_region = \
        np.where(abs(Fr_lstTmStp.sgndDist) < sim_parameters.tmStpPrefactor * 6.66 * (
                Fr_lstTmStp.mesh.hx ** 2 + Fr_lstTmStp.mesh.hy ** 2) ** 0.5)[0]
        # the search region outwards from the front position at last time step
        pstv_region = np.where(Fr_lstTmStp.sgndDist[front_region] >= -(Fr_lstTmStp.mesh.hx ** 2 +
                                                                       Fr_lstTmStp.mesh.hy ** 2) ** 0.5)[0]
        # the search region inwards from the front position at last time step
        ngtv_region = np.where(Fr_lstTmStp.sgndDist[front_region] < 0)[0]

        # SOLVE EIKONAL eq via Fast Marching Method starting to get the distance from tip for each cell.
        SolveFMM(sgndDist_k,
                 Fr_lstTmStp.EltRibbon,
                 Fr_lstTmStp.EltChannel,
                 Fr_lstTmStp.mesh,
                 front_region[pstv_region],
                 front_region[ngtv_region])


        # if some elements remain unevaluated by fast marching method. It happens with unrealistic fracture geometry.
        # todo: not satisfied with why this happens. need re-examining
        if max(sgndDist_k[front_region[pstv_region]]) == 1e10 or max(sgndDist_k[front_region[pstv_region]]) == 1e10:
            exitstatus = 2
            return exitstatus, None

        # do it only once if KprimeFunc is not provided
        if Material_properties.K1cFunc is None:
            break

        # norm = np.linalg.norm(1 - abs(l_m1 / sgndDist_k[Fr_lstTmStp.EltRibbon]))
        norm = np.linalg.norm(1 - abs(Kprime_k / Kprime_km1))/Kprime_k.size**0.5
        if norm < sim_parameters.toleranceToughness:
            if sim_parameters.verbosity > 1:
                print("converged...\ntoughness iteration converged after " + repr(itr - 1) + " iterations; exiting norm"
                                                                                             " " + repr(norm))
            break

        Kprime_km1 = np.copy(Kprime_k)
        if sim_parameters.verbosity > 1:
            print("iterating on toughness... norm "+repr(norm))
        itr += 1

    # if itr == sim_parameters.maxToughnessItr:
    #     exitstatus = 10
    #     return exitstatus, None

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
            exitstatus = 12
            return exitstatus, None
            # Fr_lstTmStp.plot_fracture('complete', 'footPrint')
            # raise SystemExit('Reached end of the grid. exiting....')

    # generate the InCrack array for the current front position
    InCrack_k = np.zeros((Fr_lstTmStp.mesh.NumberOfElts,), dtype=np.int8)
    InCrack_k[Fr_lstTmStp.EltChannel] = 1
    InCrack_k[EltsTipNew] = 1

    # the velocity of the front for the current front position
    # todo: not accurate on the first iteration. needed to be checked
    Vel_k = -(sgndDist_k[EltsTipNew] - Fr_lstTmStp.sgndDist[EltsTipNew]) / timeStep

    # Calculate filling fraction of the tip cells for the current fracture position
    FillFrac_k = Integral_over_cell(EltsTipNew,
                                alpha_k,
                                l_k,
                                Fr_lstTmStp.mesh,
                                'A') / Fr_lstTmStp.mesh.EltArea


    # todo !!! Hack: This check rounds the filling fraction to 1 if it is not bigger than 1 + 1e-4 (up to 4 figures)
    FillFrac_k[np.logical_and(FillFrac_k > 1.0, FillFrac_k < 1 + 1e-4)] = 1.0

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

    if sim_parameters.verbosity > 1:
        print('Solving the EHL system with the new trial footprint')

    # Calculating toughness at tip to be used to calculate the volume integral in the tip cells
    if not Material_properties.K1cFunc is None:
        zrVrtx_newTip = find_zero_vertex(EltsTipNew, sgndDist_k, Fr_lstTmStp.mesh)
        Kprime_tip = (32 / math.pi) ** 0.5 * get_toughness_from_zeroVertex(EltsTipNew,
                                                 Fr_lstTmStp.mesh,
                                                 Material_properties,
                                                 alpha_k,
                                                 l_k,
                                                 zrVrtx_newTip)
    else:
        Kprime_tip = None

    if performance_node is not None:
        performance_node.iterations += 1
        PerfNode_wTip = IterationProperties(itr_type="tip volume")
    else:
        PerfNode_wTip = None

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
        wTip = Integral_over_cell(EltsTipNew,
                              alpha_k,
                              l_k,
                              Fr_lstTmStp.mesh,
                              sim_parameters.get_tipAsymptote(),
                              mat_prop=Material_properties,
                              Vel=Vel_k,
                              Kprime=Kprime_tip,
                              stagnant=stagnant,
                              KIPrime=KIPrime
                              ) / Fr_lstTmStp.mesh.EltArea
    else:
        # Calculate average width in the tip cells by integrating tip asymptote
        wTip = Integral_over_cell(EltsTipNew,
                              alpha_k,
                              l_k,
                              Fr_lstTmStp.mesh,
                              sim_parameters.get_tipAsymptote(),
                              mat_prop=Material_properties,
                              Vel=Vel_k,
                              Kprime=Kprime_tip) / Fr_lstTmStp.mesh.EltArea

    # # check if the tip volume has gone into negative
    # smallNgtvWTip = np.where(np.logical_and(wTip < 0, wTip > -1e-4 * np.mean(wTip)))
    # if np.asarray(smallNgtvWTip).size > 0:
    #     #warnings.warn("Small negative volume integral(s) received, ignoring "+repr(wTip[smallngtvwTip])+' ...')
    #     wTip[smallNgtvWTip] = abs(wTip[smallNgtvWTip])


    if (wTip < 0).any():
        exitstatus = 4
        return exitstatus, None

    if performance_node is not None:
        performance_node.iterations += 1
        PerfNode_linSolve = IterationProperties(itr_type="Linear solve iterations")
        PerfNode_linSolve.subIterations = []
    else:
        PerfNode_linSolve = None

    C_EltTip = C[np.ix_(EltsTipNew[partlyFilledTip], EltsTipNew[partlyFilledTip])]  # keeping the tip element entries to restore current
    #  tip correction. This is done to avoid copying the full elasticity matrix.

    # filling fraction correction for element in the tip region
    FillF = FillFrac_k[partlyFilledTip]
    for e in range(0, len(partlyFilledTip)):
        r = FillF[e] - .25
        if r < 0.1:
            r = 0.1
        ac = (1 - r) / r
        C[EltsTipNew[partlyFilledTip[e]], EltsTipNew[partlyFilledTip[e]]] *= (1. + ac * np.pi / 4.)

    A, b = MakeEquationSystem_volumeControl_extendedFP(Fr_lstTmStp.w,
                                                wTip,
                                                Fr_lstTmStp.EltChannel,
                                                EltsTipNew,
                                                C,
                                                timeStep,
                                                Qin,
                                                Fr_lstTmStp.mesh.EltArea)

    sol = np.linalg.solve(A, b)

    # regain original C (without filling fraction correction)
    C[np.ix_(EltsTipNew[partlyFilledTip], EltsTipNew[partlyFilledTip])] = C_EltTip

    if PerfNode_linSolve is not None:
        PerfNode_linSolve.CpuTime_end = time.time()
        performance_node.subIterations[2].append(PerfNode_linSolve)

    # the fracture to be returned for k plus 1 iteration
    Fr_kplus1 = copy.deepcopy(Fr_lstTmStp)

    Fr_kplus1.time += timeStep

    Fr_kplus1.w[Fr_lstTmStp.EltChannel] += sol[np.arange(Fr_lstTmStp.EltChannel.size)]
    # Fr_kplus1.w[Fr_lstTmStp.EltChannel] = sol[np.arange(Fr_lstTmStp.EltChannel.size)]
    Fr_kplus1.w[EltsTipNew] = wTip

    # check if the new width is valid
    if np.isnan(Fr_kplus1.w).any():
        exitstatus = 5
        return exitstatus, None

    # todo: clean this up as it might blow up !    -> we need a linear solver with constraint to handle pinch point properly.
    if (Fr_kplus1.w < 0).any():
        # print(repr(np.where((Fr_kplus1.w < 0))))
        # print(repr(Fr_kplus1.w[np.where((Fr_kplus1.w < 0))[0]]))
        exitstatus = 5
        return exitstatus, None

    Fr_kplus1.FillF = FillFrac_k[partlyFilledTip]
    Fr_kplus1.EltChannel = EltChannel_k
    Fr_kplus1.EltTip = EltTip_k
    Fr_kplus1.EltCrack = EltCrack_k
    Fr_kplus1.EltRibbon = EltRibbon_k
    Fr_kplus1.ZeroVertex = zrVertx_k

    # pressure evaluated by dot product of width and elasticity matrix
    Fr_kplus1.p = np.zeros((Fr_lstTmStp.mesh.NumberOfElts,), dtype=np.float64)
    Fr_kplus1.p[EltCrack_k] = sol[-1]
    Fr_kplus1.sgndDist = sgndDist_k
    Fr_kplus1.sgndDist_last = Fr_lstTmStp.sgndDist
    Fr_kplus1.timeStep_last = timeStep

    Fr_kplus1.alpha = alpha_k[partlyFilledTip]
    Fr_kplus1.l = l_k[partlyFilledTip]
    Fr_kplus1.v = Vel_k[partlyFilledTip]

    Fr_kplus1.InCrack = InCrack_k

    Fr_kplus1.process_fracture_front()
    Fr_kplus1.FractureVolume = np.sum(Fr_kplus1.w) * (Fr_kplus1.mesh.EltArea)


    exitstatus = 1
    return exitstatus, Fr_kplus1

#-----------------------------------------------------------------------------------------------------------------------


def time_step_explicit_front_volumeControl(Fr_lstTmStp, C, timeStep, Qin, Material_properties, sim_parameters,
                                           performance_node=None):
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
                                    11      -- Projection could not be found
                                    12      -- Reached end of grid
                                    13      -- Leak off can't be evaluated

        Fracture object:            fracture after advancing time step.
    """

    sgndDist_k = 1e10 * np.ones((Fr_lstTmStp.mesh.NumberOfElts,), float)  # Initializing the cells with maximum
    # float value. (algorithm requires inf)
    sgndDist_k[Fr_lstTmStp.EltChannel] = 0  # for cells inside the fracture

    sgndDist_k[Fr_lstTmStp.EltTip] = Fr_lstTmStp.sgndDist[Fr_lstTmStp.EltTip] - (timeStep *
                                                                                 Fr_lstTmStp.v)

    front_region = np.where(abs(Fr_lstTmStp.sgndDist) < sim_parameters.tmStpPrefactor * 6.66 *(
                Fr_lstTmStp.mesh.hx ** 2 + Fr_lstTmStp.mesh.hy ** 2) ** 0.5)[0]
    # the search region outwards from the front position at last time step
    pstv_region = np.where(Fr_lstTmStp.sgndDist[front_region] >= -(Fr_lstTmStp.mesh.hx ** 2 +
                                                                   Fr_lstTmStp.mesh.hy ** 2) ** 0.5)[0]
    # the search region inwards from the front position at last time step
    ngtv_region = np.where(Fr_lstTmStp.sgndDist[front_region] < 0)[0]

    # SOLVE EIKONAL eq via Fast Marching Method starting to get the distance from tip for each cell.
    SolveFMM(sgndDist_k,
             Fr_lstTmStp.EltTip,
             Fr_lstTmStp.EltCrack,
             Fr_lstTmStp.mesh,
             front_region[pstv_region],
             front_region[ngtv_region])

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
            exitstatus = 12
            return exitstatus, None

    # generate the InCrack array for the current front position
    InCrack_k = np.zeros((Fr_lstTmStp.mesh.NumberOfElts,), dtype=np.int8)
    InCrack_k[Fr_lstTmStp.EltChannel] = 1
    InCrack_k[EltsTipNew] = 1

    # Calculate filling fraction of the tip cells for the current fracture position
    FillFrac_k = Integral_over_cell(EltsTipNew,
                                    alpha_k,
                                    l_k,
                                    Fr_lstTmStp.mesh,
                                    'A') / Fr_lstTmStp.mesh.EltArea

    # todo !!! Hack: This check rounds the filling fraction to 1 if it is not bigger than 1 + 1e-4 (up to 4 figures)
    FillFrac_k[np.logical_and(FillFrac_k > 1.0, FillFrac_k < 1 + 1e-4)] = 1.0

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

    if sim_parameters.verbosity > 1:
        print('Solving the EHL system with the new trial footprint')

    # Calculating toughness at tip to be used to calculate the volume integral in the tip cells
    if not Material_properties.K1cFunc is None:
        zrVrtx_newTip = find_zero_vertex(EltsTipNew, sgndDist_k, Fr_lstTmStp.mesh)
        Kprime_tip = (32 / math.pi) ** 0.5 * get_toughness_from_zeroVertex(EltsTipNew,
                                                                           Fr_lstTmStp.mesh,
                                                                           Material_properties,
                                                                           alpha_k,
                                                                           l_k,
                                                                           zrVrtx_newTip)
    else:
        Kprime_tip = None

    # the velocity of the front for the current front position
    # todo: not accurate on the first iteration. needed to be checked
    Vel_k = -(sgndDist_k[EltsTipNew] - Fr_lstTmStp.sgndDist[EltsTipNew]) / timeStep

    # create a performance node for the root finding to get tip volume
    if performance_node is not None:
        performance_node.iterations += 1
        PerfNode_wTip = IterationProperties(itr_type="tip volume")
    else:
        PerfNode_wTip = None

    # stagnant tip cells i.e. the tip cells whose distance from front has not changed.
    stagnant = Vel_k < 1e-14
    if stagnant.any() and not sim_parameters.get_tipAsymptote() is 'U':
        print("Stagnant front is only supported with universal tip asymptote")
        stagnant = np.full((EltsTipNew.size,), False, dtype=bool)

    if stagnant.any():
        # if any tip cell with stagnant front calculate stress intensity factor for stagnant cells
        KIPrime = StressIntensityFactor(Fr_lstTmStp.w,
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

        wTip = Integral_over_cell(EltsTipNew,
                                  alpha_k,
                                  l_k,
                                  Fr_lstTmStp.mesh,
                                  sim_parameters.get_tipAsymptote(),
                                  frac=Fr_lstTmStp,
                                  mat_prop=Material_properties,
                                  Vel=Vel_k,
                                  stagnant=stagnant,
                                  KIPrime=KIPrime) / Fr_lstTmStp.mesh.EltArea
    else:
        # Calculate average width in the tip cells by integrating tip asymptote
        wTip = Integral_over_cell(EltsTipNew,
                                  alpha_k,
                                  l_k,
                                  Fr_lstTmStp.mesh,
                                  sim_parameters.get_tipAsymptote(),
                                  frac=Fr_lstTmStp,
                                  mat_prop=Material_properties,
                                  Vel=Vel_k,
                                  Kprime=Kprime_tip,
                                  stagnant=stagnant) / Fr_lstTmStp.mesh.EltArea

    # # check if the tip volume has gone into negative
    # smallNgtvWTip = np.where(np.logical_and(wTip < 0, wTip > -1e-4 * np.mean(wTip)))
    # if np.asarray(smallNgtvWTip).size > 0:
    #     #                    warnings.warn("Small negative volume integral(s) received, ignoring "+repr(wTip[smallngtvwTip])+' ...')
    #     wTip[smallNgtvWTip] = abs(wTip[smallNgtvWTip])

    if (wTip < 0).any() or sum(wTip) == 0.:
        exitstatus = 4
        return exitstatus, None

    A, b = MakeEquationSystem_volumeControl_extendedFP(Fr_lstTmStp.w,
                                                       wTip,
                                                       Fr_lstTmStp.EltChannel,
                                                       EltsTipNew,
                                                       C,
                                                       timeStep,
                                                       Qin,
                                                       Fr_lstTmStp.mesh.EltArea)

    if performance_node is not None:
        performance_node.iterations += 1
        PerfNode_linSolve = IterationProperties(itr_type="Linear solve iterations")
        PerfNode_linSolve.subIterations = []
    else:
        PerfNode_linSolve = None

    sol = np.linalg.solve(A, b)

    if PerfNode_linSolve is not None:
        PerfNode_linSolve.CpuTime_end = time.time()
        performance_node.subIterations[2].append(PerfNode_linSolve)

    # the fracture to be returned for k plus 1 iteration
    Fr_kplus1 = copy.deepcopy(Fr_lstTmStp)
    Fr_kplus1.time += timeStep
    Fr_kplus1.w[Fr_lstTmStp.EltChannel] += sol[np.arange(Fr_lstTmStp.EltChannel.size)]
    Fr_kplus1.w[EltsTipNew] = wTip

    # check if the new width is valid
    if np.isnan(Fr_kplus1.w).any():
        exitstatus = 5
        return exitstatus, None

    if (
            Fr_kplus1.w < 0).any():  # todo: clean this up as it might blow up !    -> we need a linear solver with constraint to handle pinch point properly.
        # print(repr(np.where((Fr_kplus1.w < 0))))
        # print(repr(Fr_kplus1.w[np.where((Fr_kplus1.w < 0))[0]]))
        exitstatus = 5
        return exitstatus, None

    Fr_kplus1.FillF = FillFrac_k[partlyFilledTip]
    Fr_kplus1.EltChannel = EltChannel_k
    Fr_kplus1.EltTip = EltTip_k
    Fr_kplus1.EltCrack = EltCrack_k
    Fr_kplus1.EltRibbon = EltRibbon_k
    Fr_kplus1.ZeroVertex = zrVertx_k

    # pressure evaluated by dot product of width and elasticity matrix
    Fr_kplus1.p[Fr_kplus1.EltCrack] = np.dot(C[np.ix_(Fr_kplus1.EltCrack, Fr_kplus1.EltCrack)],
                                             Fr_kplus1.w[Fr_kplus1.EltCrack])
    Fr_kplus1.alpha = alpha_k[partlyFilledTip]
    Fr_kplus1.l = l_k[partlyFilledTip]
    Fr_kplus1.InCrack = InCrack_k
    Fr_kplus1.process_fracture_front()
    Fr_kplus1.FractureVolume = np.sum(Fr_kplus1.w) * (Fr_kplus1.mesh.EltArea)

    if sim_parameters.frontAdvancing == 'explicit':
        if sim_parameters.verbosity > 1:
            print("Solved...\nFinding velocity of front...")

        itr = 0
        if not Material_properties.K1cFunc is None:
            alpha_ribbon = projection_from_ribbon(Fr_lstTmStp.EltRibbon,
                                                  Fr_lstTmStp.EltChannel,
                                                  Fr_lstTmStp.mesh,
                                                  sgndDist_k)
            Kprime_k = (32 / math.pi) ** 0.5 * get_toughness_from_cellCenter(alpha_ribbon,
                                                                             sgndDist_k,
                                                                             Fr_lstTmStp.EltRibbon,
                                                                             Material_properties,
                                                                             Fr_lstTmStp.mesh)
            # Kprime from last iteration; starts with zero
            Kprime_km1 = 0 * np.copy(Kprime_k)

        # toughness iteration loop
        while itr < sim_parameters.maxToughnessItr:

            sgndDist_km1 = np.copy(sgndDist_k)
            l_m1 = sgndDist_km1[Fr_lstTmStp.EltRibbon]

            if not Material_properties.K1cFunc is None:
                alpha_ribbon = projection_from_ribbon(Fr_lstTmStp.EltRibbon,
                                                      Fr_lstTmStp.EltChannel,
                                                      Fr_lstTmStp.mesh,
                                                      sgndDist_k)
                if np.isnan(alpha_ribbon).any():
                    exitstatus = 11
                    return exitstatus, None
                # under relaxing toughnesss
                Kprime_k = 0.3 * Kprime_k + 0.7 * get_toughness_from_cellCenter(alpha_ribbon,
                                                                                sgndDist_k,
                                                                                Fr_lstTmStp.EltRibbon,
                                                                                Material_properties,
                                                                                Fr_lstTmStp.mesh) * (32 / math.pi) ** 0.5

                if np.isnan(Kprime_k).any():
                    exitstatus = 11
                    return exitstatus, None
            else:
                Kprime_k = None

            # Initialization of the signed distance in the ribbon element - by inverting the tip asymptotics
            sgndDist_k = 1e10 * np.ones((Fr_lstTmStp.mesh.NumberOfElts,), float)  # Initializing the cells with extremely
            # large float value. (algorithm requires inf)

            sgndDist_k[Fr_lstTmStp.EltRibbon] = - TipAsymInversion(Fr_kplus1.w,
                                                                   Fr_lstTmStp,
                                                                   Material_properties,
                                                                   sim_parameters,
                                                                   timeStep,
                                                                   Kprime_k=Kprime_k)

            # if tip inversion returns nan
            if np.isnan(sgndDist_k[Fr_lstTmStp.EltRibbon]).any():
                exitstatus = 7
                return exitstatus, None

            # Check if the front is receding
            sgndDist_k[Fr_lstTmStp.EltRibbon] = np.minimum(sgndDist_k[Fr_lstTmStp.EltRibbon],
                                                           Fr_lstTmStp.sgndDist[Fr_lstTmStp.EltRibbon])

            # region expected to have the front after propagation. The signed distance of the cells only in this region will
            # evaluated with the fast marching method to avoid unnecessary computation cost
            front_region = np.where(abs(Fr_lstTmStp.sgndDist) < sim_parameters.tmStpPrefactor * 6.66 * (
                    Fr_lstTmStp.mesh.hx ** 2 + Fr_lstTmStp.mesh.hy ** 2) ** 0.5)[0]
            # the search region outwards from the front position at last time step
            pstv_region = np.where(Fr_lstTmStp.sgndDist[front_region] >= -(Fr_lstTmStp.mesh.hx ** 2 +
                                                                           Fr_lstTmStp.mesh.hy ** 2) ** 0.5)[0]
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

            # do it only once if not anisotropic
            if not Material_properties.anisotropic:
                break

            # norm = np.linalg.norm(1 - abs(l_m1/sgndDist_k[Fr_lstTmStp.EltRibbon]))
            norm = np.linalg.norm(1 - abs(Kprime_k / Kprime_km1))
            if norm < sim_parameters.toleranceToughness:
                if sim_parameters.verbosity > 1:
                    print("toughness iteration converged after " + repr(itr - 1) + " iterations; exiting norm " +
                          repr(norm))
                break

            Kprime_km1 = np.copy(Kprime_k)
            if sim_parameters.verbosity > 1:
                print("iterating on toughness... norm " + repr(norm))
            itr += 1

        # if itr == sim_parameters.maxToughnessItr:
        #     exitstatus = 10
        #     return exitstatus, None

        Fr_kplus1.v = -(sgndDist_k[Fr_kplus1.EltTip] - Fr_lstTmStp.sgndDist[Fr_kplus1.EltTip]) / timeStep
        if sim_parameters.saveRegime:
            regime_t = find_regime(Fr_kplus1.w, Fr_lstTmStp, Material_properties, sim_parameters, timeStep, Kprime_k,
                                   -sgndDist_k[Fr_lstTmStp.EltRibbon])
            Fr_kplus1.regime = np.vstack((regime_t, Fr_lstTmStp.EltRibbon))
    else:
        Fr_kplus1.v = None

    Fr_kplus1.sgndDist = sgndDist_k
    Fr_kplus1.sgndDist_last = Fr_lstTmStp.sgndDist
    Fr_kplus1.timeStep_last = timeStep

    exitstatus = 1
    return exitstatus, Fr_kplus1