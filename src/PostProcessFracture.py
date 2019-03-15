#
# This file is part of PyFrac.
#
# Created by Brice Lecampion on 12.06.17.
# Copyright (c) ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory, 2016-2019.  All rights reserved.
# See the LICENSE.TXT file for more details.
#
#
# Post-process scripts to plot results for a fracture

# local

from src.Utility import ReadFracture
from src.HFAnalyticalSolutions import HF_analytical_sol, get_fracture_dimensions_analytical
from src.Labels import *

import numpy as np
from scipy.interpolate import griddata
import dill
import os
import re
import sys


if 'win32' in sys.platform or 'win64' in sys.platform:
    slash = '\\'
else:
    slash = '/'

#-----------------------------------------------------------------------------------------------------------------------


def load_fractures(address=None, sim_name='simulation', time_period=0.0, time_srs=None, step_size=1):
    """
    This function returns a list of the fractures. If address and simulation name are not provided, results from the
    default address and having the default name will be loaded.

    Args:
        address (string):               -- the folder address containing the saved files. If it is not provided,
                                            simulation from the default folder (_simulation_data_PyFrac) will be loaded.
        sim_name (string):              -- the simulation name from which the fractures are to be loaded. If not
                                            provided, simulation with the default name (Simulation) will be loaded.
        time_period (float):            -- time period between two successive fractures to be loaded. if not provided,
                                            all fractures will be loaded.
        time_srs (ndarray):             -- if provided, the fracture stored at the closest time after the given times
                                            will be loaded.
    Returns:
        (list):                         -- a list of fractures.

    """

    print('Returning fractures...')

    if address is None:
        address = '.' + slash + '_simulation_data_PyFrac'

    if address[-1] is not slash:
        address = address + slash

    if isinstance(time_srs, float) or isinstance(time_srs, int):
        time_srs = np.array([time_srs])
    elif isinstance(time_srs, list):
        time_srs = np.array(time_srs)

    sim_full_name = None
    if re.match('\d+-\d+-\d+__\d+_\d+_\d+', sim_name[-20:]):
        sim_full_name = sim_name
    else:
        simulations = os.listdir(address)
        recent_sim_time = 0
        for i in simulations:
            if re.match(sim_name + '__\d+-\d+-\d+__\d+_\d+_\d+', i):

                filename = address + i + slash + 'properties'
                try:
                    with open(filename, 'rb') as input:
                        (Solid, Fluid, Injection, SimulProp) = dill.load(input)
                except FileNotFoundError:
                    raise SystemExit('Data not found. The address might be incorrect')

                if SimulProp.get_timeStamp() > recent_sim_time:
                    recent_sim_time = SimulProp.get_timeStamp()
                    sim_full_name = i

    if sim_full_name is None:
        raise ValueError('Simulation not found! The address might be incorrect.')

    # read properties
    filename = address + sim_full_name + slash + 'properties'
    try:
        with open(filename, 'rb') as input:
            properties = dill.load(input)
    except FileNotFoundError:
        raise SystemExit('Data not found. The address might be incorrect')

    fileNo = 0
    next_t = 0.0
    t_srs_indx = 0
    fracture_list = []

    t_srs_given = isinstance(time_srs, np.ndarray) #time series is given
    if t_srs_given:
        if len(time_srs) == 0:
            return fracture_list
        next_t = time_srs[t_srs_indx]

    # time at wich the first fracture file was modified
    ff = None
    while fileNo < 5000:

        # trying to load next file. exit loop if not found
        try:
            ff = ReadFracture(address + sim_full_name + slash + sim_full_name + '_file_' + repr(fileNo))
        except FileNotFoundError:
            break

        fileNo += step_size

        if 1. - next_t / ff.time >= -0.001:
            # if the current fracture time has advanced the output time period
            print('Returning fracture at ' + repr(ff.time) + ' s')

            fracture_list.append(ff)

            if t_srs_given:
                if t_srs_indx < len(time_srs) - 1:
                    t_srs_indx += 1
                    next_t = time_srs[t_srs_indx]
                if ff.time > max(time_srs):
                    break
            else:
                next_t = ff.time + time_period

    if fileNo >= 5000:
        raise SystemExit('too many files.')

    if len(fracture_list) == 0:
        raise ValueError("Fracture list is empty")

    return fracture_list, properties


#-----------------------------------------------------------------------------------------------------------------------

def get_fracture_variable(fracture_list, variable, edge=4, return_time=True):


    variable_list = []
    time_srs = []

    if variable is 'time' or variable is 't':
        for i in fracture_list:
            variable_list.append(i.time)
            time_srs.append(i.time)
        return variable_list

    elif variable is 'width' or variable is 'w':
        for i in fracture_list:
            variable_list.append(i.w)
            time_srs.append(i.time)

    elif variable is 'fluid pressure' or variable is 'pf':
        for i in fracture_list:
            variable_list.append(i.pFluid)
            time_srs.append(i.time)

    elif variable is 'Net pressure' or variable is 'pn':
        for i in fracture_list:
            variable_list.append(i.pNet)
            time_srs.append(i.time)

    elif variable is 'front velocity' or variable is 'v':
        for i in fracture_list:
            vel = np.full((i.mesh.NumberOfElts, ), np.nan)
            vel[i.EltTip] = i.v
            variable_list.append(vel)
            time_srs.append(i.time)

    elif variable is 'Reynolds number' or variable is 'Re':
        if fracture_list[-1].ReynoldsNumber is None:
            raise SystemExit(err_var_not_saved)
        for i in fracture_list:
            if edge < 0 or edge > 4:
                raise ValueError('Edge can be an integer between and including 0 and 4.')
            if edge < 4:
                variable_list.append(i.ReynoldsNumber[edge])
                time_srs.append(i.time)
            elif i.ReynoldsNumber is not None:
                variable_list.append(np.mean(i.ReynoldsNumber, axis=0))
                time_srs.append(i.time)
            else:
                variable_list.append(np.full((i.mesh.NumberOfElts, ), np.nan))

    elif variable is 'fluid flux' or variable is 'ff':
        if fracture_list[-1].fluidFlux is None:
            raise SystemExit(err_var_not_saved)
        for i in fracture_list:
            if edge < 0 or edge > 4:
                raise ValueError('Edge can be an integer between and including 0 and 4.')
            if edge < 4:
                variable_list.append(i.fluidFlux[edge])
                time_srs.append(i.time)
            elif i.fluidFlux is not None:
                variable_list.append(np.mean(i.fluidFlux, axis=0))
                time_srs.append(i.time)
            else:
                variable_list.append(np.full((i.mesh.NumberOfElts,), np.nan))

    elif variable is 'fluid velocity' or variable is 'fv':
        if fracture_list[-1].fluidVelocity is None:
            raise SystemExit(err_var_not_saved)
        for i in fracture_list:
            if edge < 0 or edge > 4:
                raise ValueError('Edge can be an integer between and including 0 and 4.')
            if edge < 4:
                variable_list.append(i.fluidVelocity[edge])
                time_srs.append(i.time)
            elif i.fluidFlux is not None:
                variable_list.append(np.mean(i.fluidVelocity, axis=0))
                time_srs.append(i.time)
            else:
                variable_list.append(np.full((i.mesh.NumberOfElts, ), np.nan))

    elif variable in ('front_dist_min', 'd_min', 'front_dist_max', 'd_max', 'front_dist_mean', 'd_mean'):
        for i in fracture_list:
            # coordinate of the zero vertex in the tip cells
            vertex_coord_tip = i.mesh.VertexCoor[i.mesh.Connectivity[i.EltTip, i.ZeroVertex]]
            if variable is 'front_dist_mean' or variable is 'd_mean':
                variable_list.append(np.mean((vertex_coord_tip[:, 0] ** 2 +
                                              vertex_coord_tip[:, 1] ** 2) ** 0.5 + i.l))
            elif variable is 'front_dist_max' or variable is 'd_max':
                variable_list.append(max((vertex_coord_tip[:, 0] ** 2 +
                                          vertex_coord_tip[:, 1] ** 2) ** 0.5 + i.l))
            elif variable is 'front_dist_min' or variable is 'd_min':
                variable_list.append(min((vertex_coord_tip[:, 0] ** 2 +
                                          vertex_coord_tip[:, 1] ** 2) ** 0.5 + i.l))
            time_srs.append(i.time)
    elif variable is 'mesh':
        for i in fracture_list:
            variable_list.append(i.mesh)
            time_srs.append(i.time)

    elif variable is 'efficiency' or variable is 'ef':
        for i in fracture_list:
            variable_list.append(i.efficiency)
            time_srs.append(i.time)
            
    elif variable is 'volume' or variable is 'V':
        for i in fracture_list:
            variable_list.append(i.FractureVolume)
            time_srs.append(i.time)
            
    elif variable is 'leaked off' or variable is 'lk':
        for i in fracture_list:
            variable_list.append(i.LkOff_vol)
            time_srs.append(i.time)
            
    elif variable is 'leaked off volume' or variable is 'lkv':
        for i in fracture_list:
            variable_list.append(sum(i.LkOff_vol[i.EltCrack]))
            time_srs.append(i.time)
            
    elif variable is 'aspect ratio' or variable is 'ar':
        for i in fracture_list:
            cells_x_axis = np.where(abs(i.mesh.CenterCoor[:, 1]) < 1e-12)[0]
            to_delete = np.where(i.mesh.CenterCoor[cells_x_axis, 0] < 0)[0]
            cells_x_axis_pstv = np.delete(cells_x_axis, to_delete)
            tipCell_x_axis = np.intersect1d(i.EltTip, cells_x_axis_pstv)
            in_tip_x = np.where(i.EltTip == tipCell_x_axis[0])[0]
    
            cells_y_axis = np.where(abs(i.mesh.CenterCoor[:, 0]) < 1e-12)[0]
            to_delete = np.where(i.mesh.CenterCoor[cells_y_axis, 1] < 0)[0]
            cells_y_axis_pstv = np.delete(cells_y_axis, to_delete)
            tipCell_y_axis = np.intersect1d(i.EltTip, cells_y_axis_pstv)
            in_tip_y = np.where(i.EltTip == tipCell_y_axis[0])[0]
    
            tipVrtxCoord = i.mesh.VertexCoor[i.mesh.Connectivity[tipCell_y_axis, 0]]
            r_y = (tipVrtxCoord[0, 0] ** 2 + tipVrtxCoord[0, 1] ** 2) ** 0.5 + i.l[in_tip_y]
            tipVrtxCoord = i.mesh.VertexCoor[i.mesh.Connectivity[tipCell_x_axis, 0]]
            r_x = (tipVrtxCoord[0, 0] ** 2 + tipVrtxCoord[0, 1] ** 2) ** 0.5 + i.l[in_tip_x]
    
            variable_list.append(r_x / r_y)
            time_srs.append(i.time)
            
    else:
        raise ValueError('The variable type is not correct.')

    if not return_time:
        return variable_list
    else:
        return variable_list, time_srs


#-----------------------------------------------------------------------------------------------------------------------

def get_fracture_variable_at_point(fracture_list, variable, point, edge=4, return_time=True):

    if variable not in supported_variables:
        raise ValueError(err_msg_variable)

    return_list = []

    var_values, time_list = get_fracture_variable(fracture_list,
                                                        variable,
                                                        edge=edge)

    if variable in unidimensional_variables:
        return_list = var_values
    else:
        for i in range(len(fracture_list)):
            if variable in ('width', 'w', 'pressure', 'p', 'fluid flux', 'ff', 'fluid velocity', \
                            'fv', 'Reynolds number', 'Re'):
                value_point = griddata(fracture_list[i].mesh.CenterCoor,
                                       var_values[i],
                                       point,
                                       method='linear',
                                       fill_value=np.nan)
                if np.isnan(value_point):
                    print('Point outside fracture.')

                return_list.append(value_point[0])

    if return_time:
        return return_list, time_list
    else:
        return return_list


#-----------------------------------------------------------------------------------------------------------------------

def get_fracture_variable_slice_interpolated(var_value, mesh, point1=None, point2=None):

    if not isinstance(var_value, np.ndarray):
        raise ValueError("Variable value should be provided in the form of numpy array with the size equal to the "
                         "number of elements in the mesh!")
    elif var_value.size != mesh.NumberOfElts:
        raise ValueError("Given array is not equal to the number of elements in mesh!")

    if point1 is None:
        point1 = np.array([-mesh.Lx, 0.])
    if point2 is None:
        point2 = np.array([mesh.Lx, 0.])

    # the code below find the extreme points of the line joining the two given points with the current mesh
    if point2[0] == point1[0]:
        point1[1] = -mesh.Ly
        point2[1] = mesh.Ly
    elif point2[1] == point1[1]:
        point1[0] = -mesh.Lx
        point2[0] = mesh.Lx
    else:
        slope = (point2[1] - point1[1]) / (point2[0] - point1[0])
        y_intrcpt_lft = slope * (-mesh.Lx - point1[0]) + point1[1]
        y_intrcpt_rgt = slope * (mesh.Lx - point1[0]) + point1[1]
        x_intrcpt_btm = (-mesh.Ly - point1[1]) / slope + point1[0]
        x_intrcpt_top = (mesh.Ly - point1[1]) / slope + point1[0]

        if abs(y_intrcpt_lft) < mesh.Ly:
            point1[0] = -mesh.Lx
            point1[1] = y_intrcpt_lft
        if y_intrcpt_lft > mesh.Ly:
            point1[0] = x_intrcpt_top
            point1[1] = mesh.Ly
        if y_intrcpt_lft < -mesh.Ly:
            point1[0] = x_intrcpt_btm
            point1[1] = -mesh.Ly

        if abs(y_intrcpt_rgt) < mesh.Ly:
            point2[0] = mesh.Lx
            point2[1] = y_intrcpt_rgt
        if y_intrcpt_rgt > mesh.Ly:
            point2[0] = x_intrcpt_top
            point2[1] = mesh.Ly
        if y_intrcpt_rgt < -mesh.Ly:
            point2[0] = x_intrcpt_btm
            point2[1] = -mesh.Ly

    sampling_points = np.hstack((np.linspace(point1[0], point2[0], 105).reshape((105, 1)),
                                 np.linspace(point1[1], point2[1], 105).reshape((105, 1))))

    value_samp_points = griddata(mesh.CenterCoor,
                                 var_value,
                                 sampling_points,
                                 method='linear',
                                 fill_value=np.nan)

    sampling_line_lft = ((sampling_points[:52, 0] - sampling_points[52, 0]) ** 2 +
                         (sampling_points[:52, 1] - sampling_points[52, 1]) ** 2) ** 0.5
    sampling_line_rgt = ((sampling_points[52:, 0] - sampling_points[52, 0]) ** 2 +
                         (sampling_points[52:, 1] - sampling_points[52, 1]) ** 2) ** 0.5
    sampling_line = np.concatenate((-sampling_line_lft, sampling_line_rgt))

    return value_samp_points, sampling_line


#-----------------------------------------------------------------------------------------------------------------------

def get_fracture_variable_slice_cell_center(var_value, mesh, point=None, orientation='horizontal'):

    if not isinstance(var_value, np.ndarray):
        raise ValueError("Variable value should be provided in the form of numpy array with the size equal to the "
                         "number of elements in the mesh!")
    elif var_value.size != mesh.NumberOfElts:
        raise ValueError("Given array is not equal to the number of elements in mesh!")

    if point is None:
        point = np.array([0., 0.])
    if orientation not in ('horizontal', 'vertical', 'increasing', 'decreasing'):
        raise ValueError("Given orientation is not supported. Possible options:\n 'horizontal', 'vertical',"
                         " 'increasing', 'decreasing'")

    zero_cell = mesh.locate_element(point[0], point[1])
    if zero_cell == np.nan:
        raise ValueError("The given point does not lie in the grid!")

    if orientation is 'vertical':
        sampling_cells = np.hstack((np.arange(zero_cell, 0, -mesh.nx)[::-1],
                                    np.arange(zero_cell, mesh.NumberOfElts, mesh.nx)))
    elif orientation is 'horizontal':
        sampling_cells = np.arange(zero_cell // mesh.nx * mesh.nx, (zero_cell // mesh.nx + 1) * mesh.nx)

    elif orientation is 'increasing':
        bottom_half = np.arange(zero_cell, 0, -mesh.nx - 1)
        bottom_half = np.delete(bottom_half, np.where(mesh.CenterCoor[bottom_half, 0] >
                                                      mesh.CenterCoor[zero_cell, 0])[0])
        top_half = np.arange(zero_cell, mesh.NumberOfElts, mesh.nx + 1)
        top_half = np.delete(top_half, np.where(mesh.CenterCoor[top_half, 0] <
                                                mesh.CenterCoor[zero_cell, 0])[0])
        sampling_cells = np.hstack((bottom_half[::-1], top_half))

    elif orientation is 'decreasing':
        bottom_half = np.arange(zero_cell, 0, -mesh.nx + 1)
        bottom_half = np.delete(bottom_half, np.where(mesh.CenterCoor[bottom_half, 0] <
                                                      mesh.CenterCoor[zero_cell, 0])[0])
        top_half = np.arange(zero_cell, mesh.NumberOfElts, mesh.nx - 1)
        top_half = np.delete(top_half, np.where(mesh.CenterCoor[top_half, 0] >
                                                      mesh.CenterCoor[zero_cell, 0])[0])
        sampling_cells = np.hstack((bottom_half[::-1], top_half))

    sampling_len = ((mesh.CenterCoor[sampling_cells[0], 0] - mesh.CenterCoor[sampling_cells[-1], 0]) ** 2 + \
                    (mesh.CenterCoor[sampling_cells[0], 1] - mesh.CenterCoor[sampling_cells[-1], 1]) ** 2) ** 0.5

    # making x-axis centered at zero for the 1D slice. Necessary to have same reference with different meshes and
    # analytical solution plots.
    sampling_line = np.linspace(0, sampling_len, len(sampling_cells)) - sampling_len / 2

    return var_value[sampling_cells], sampling_line, sampling_cells


#-----------------------------------------------------------------------------------------------------------------------

def get_HF_analytical_solution(regime, variable, mat_prop, inj_prop, mesh=None, fluid_prop=None,
                                time_srs=None, length_srs=None, h=None, samp_cell=None, gamma=None):

    if time_srs is None and length_srs is None:
        raise ValueError('Either time series or lengths series is to be provided.')

    if regime is 'E_K':
        Kc_1 = mat_prop.Kc1
    else:
        Kc_1 = None

    if regime is 'E_E':
        Cij = mat_prop.Cij
    else:
        Cij = None

    if regime is 'MDR':
        density = fluid_prop.density
    else:
        density = None

    if regime in ['M', 'MDR']:
        if fluid_prop is None:
            raise ValueError('Fluid properties required for \'M\' type analytical solution')
        muPrime = fluid_prop.muPrime
    else:
        muPrime = None

    if samp_cell is None:
        samp_cell = int(len(mat_prop.Kprime) / 2)

    if time_srs is not None:
        srs_length = len(time_srs)
    else:
        srs_length = len(length_srs)

    mesh_list = []
    return_list = []

    for i in range(srs_length):

        if length_srs is not None:
            length = length_srs[i]
        else:
            length = None

        if time_srs is not None:
            time = time_srs[i]
        else:
            time = None

        if variable in ('time', 't', 'width', 'w', 'pressure', 'p', 'front velocity', 'v'):

            if mesh is None and variable in ('width', 'w', 'pressure', 'p'):
                x_len, y_len = get_fracture_dimensions_analytical_with_properties(regime,
                                                                                  time_srs[i],
                                                                                  mat_prop,
                                                                                  inj_prop,
                                                                                  fluid_prop=fluid_prop,
                                                                                  h=h,
                                                                                  samp_cell=samp_cell,
                                                                                  gamma=gamma)

                from src.CartesianMesh import CartesianMesh
                mesh_i = CartesianMesh(x_len, y_len, 151, 151)
            else:
                mesh_i = mesh
            mesh_list.append(mesh_i)

            t, r, p, w, v, actvElts = HF_analytical_sol(regime,
                                                        mesh_i,
                                                        mat_prop.Eprime,
                                                        inj_prop.injectionRate[1,0],
                                                        inj_point=inj_prop.sourceCoordinates,
                                                        muPrime=muPrime,
                                                        Kprime=mat_prop.Kprime[samp_cell],
                                                        Cprime=mat_prop.Cprime[samp_cell],
                                                        length=length,
                                                        t=time,
                                                        Kc_1=Kc_1,
                                                        h=h,
                                                        density=density,
                                                        Cij=Cij,
                                                        gamma=gamma,
                                                        required=required_string[variable])

            if variable is 'time' or variable is 't':
                return_list.append(t)
            elif variable is 'width' or variable is 'w':
                return_list.append(w)
            elif variable is 'pressure' or variable is 'p':
                return_list.append(p)
            elif variable is 'front velocity' or variable is 'v':
                return_list.append(v)

        elif variable in ('front_dist_min', 'd_min', 'front_dist_max', 'd_max', 'front_dist_mean', 'd_mean',
                          'radius', 'r'):
            x_len, y_len = get_fracture_dimensions_analytical_with_properties(regime,
                                                                              time,
                                                                              mat_prop,
                                                                              inj_prop,
                                                                              fluid_prop=fluid_prop,
                                                                              h=h,
                                                                              samp_cell=samp_cell,
                                                                              gamma=gamma)
            if variable is 'radius' or variable is 'r':
                return_list.append(x_len)
            elif variable is 'front_dist_min' or variable is 'd_min':
                return_list.append(y_len)
            elif variable is 'front_dist_max' or variable is 'd_max':
                return_list.append(x_len)
            elif variable is 'front_dist_mean' or variable is 'd_mean':
                if regime in ('E_K', 'E_E'):
                    raise ValueError('Mean distance not available.')
                else:
                    return_list.append(x_len)
        else:
            raise ValueError('The variable type is not correct or the anayltical solution not available.')

    return return_list, mesh_list


#-----------------------------------------------------------------------------------------------------------------------

def get_HF_analytical_solution_at_point(regime, variable, point, mat_prop, inj_prop, fluid_prop=None, time_srs=None,
                                        length_srs=None, h=None, samp_cell=None, gamma=None):

    values_point = []

    if time_srs is not None:
        srs_length = len(time_srs)
    else:
        srs_length = len(length_srs)

    from src.CartesianMesh import CartesianMesh
    if point == [0., 0.]:
        mesh_Lx = 1.
        mesh_Ly = 1.
    else:
        mesh_Lx = 2 * abs(point[0])
        mesh_Ly = 2 * abs(point[1])
    mesh = CartesianMesh(mesh_Lx, mesh_Ly, 5, 5)

    for i in range(srs_length):

        if time_srs is not None:
            time = [time_srs[i]]
        else:
            time = None

        if length_srs is not None:
            length = [length_srs[i]]
        else:
            length = None

        value_mesh, mesh_list = get_HF_analytical_solution(regime,
                                                        variable,
                                                        mat_prop,
                                                        inj_prop,
                                                        mesh=mesh,
                                                        fluid_prop=fluid_prop,
                                                        time_srs=time,
                                                        length_srs=length,
                                                        h=h,
                                                        samp_cell=samp_cell,
                                                        gamma=gamma)


        if point == [0., 0.]:
            values_point.append(value_mesh[0][mesh_list[0].CenterElts])
        else:
            value_point = value_mesh[0][18]
            values_point.append(value_point)

    return values_point

#-----------------------------------------------------------------------------------------------------------------------

def get_fracture_dimensions_analytical_with_properties(regime, time_srs, mat_prop, inj_prop, fluid_prop=None,
                                              h=None, samp_cell=None, gamma=None):


    if regime is 'E_K':
        Kc_1 = mat_prop.Kc1
    else:
        Kc_1 = None

    if regime is 'MDR':
        density = fluid_prop.density
    else:
        density = None

    if regime in ('M', 'Mt', 'PKN', 'MDR'):
        if fluid_prop is None:
            raise ValueError('Fluid properties required to evaluate analytical solution')
        muPrime = fluid_prop.muPrime
    else:
        muPrime = None

    if samp_cell is None:
        samp_cell = int(len(mat_prop.Kprime) / 2)

    x_len, y_len = get_fracture_dimensions_analytical(regime,
                                                      np.max(time_srs),
                                                      mat_prop.Eprime,
                                                      inj_prop.injectionRate[1, 0],
                                                      muPrime,
                                                      Kprime=mat_prop.Kprime[samp_cell],
                                                      Cprime=mat_prop.Cprime[samp_cell],
                                                      Kc_1=Kc_1,
                                                      h=h,
                                                      density=density,
                                                      gamma=gamma)

    return x_len, y_len

#-----------------------------------------------------------------------------------------------------------------------
