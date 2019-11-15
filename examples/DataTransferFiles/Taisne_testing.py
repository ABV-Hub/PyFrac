# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Haseeb Zia on Fri June 16 17:49:21 2017.
Copyright (c) "ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory", 2016-2019. All rights
reserved. See the LICENSE.TXT file for more details.
"""

import numpy as np

# local imports
from mesh import CartesianMesh
from properties import MaterialProperties, FluidProperties, InjectionProperties, SimulationProperties
from fracture import Fracture
from controller import Controller
from fracture_initialization import Geometry, InitializationParameters
from elasticity import load_isotropic_elasticity_matrix
import time
# creating mesh
Ly = 0.2
Mesh = CartesianMesh(0.045, Ly, 41,181)

# solid properties
nu = 0.5                           # Poisson's ratio
youngs_mod = 3402                 # Young's modulus
Eprime = youngs_mod / (1 - nu ** 2) # plain strain modulus


def sigmaO_func(x, y):
    """ This function provides the confining stress over the domain"""
    density_high = 1000
    density_low = 2400
    #layer = 1000
    #Ly = 0.25
    #if y > layer:
        #return (Ly - y) * density_low * 9.8
    # only dependant on the depth
    #return (Ly - y) * density_high * 9.8 - (Ly - layer) * (density_high - density_low) * 9.8
    return (Ly - y) * density_high * 9.81

# material properties
Solid = MaterialProperties(Mesh,
                           Eprime,
                           toughness=0.95 * np.sqrt(youngs_mod),
                           confining_stress_func=sigmaO_func,
                           minimum_width=1e-5)

# injection parameters
Q0 = np.asarray([[0.0,0.1],
                [0.0001,    0]])  # injection rate
Injection = InjectionProperties(Q0,
                                Mesh,
                                source_coordinates=[0, 0.160])

# fluid properties
Fluid = FluidProperties(viscosity=1e-3, density=1373)

# simulation properties
simulProp = SimulationProperties()
simulProp.finalTime = 1e10#4.5e3
#simulProp.frontAdvancing = 'implicit'  # the time at which the simulation stops
simulProp.set_outputFolder("./Data/neutral_buoyancy") # the disk address where the files are saved
simulProp.gravity = True                    # set up the gravity flag
simulProp.tolFractFront = 3e-3              # increase the tolerance for fracture front iteration
simulProp.plotTSJump = 1                    # plot every fourth time step
simulProp.saveTSJump = 5                    # save every second time step
simulProp.maxSolverItrs = 200
simulProp.maxReattempts = 10
simulProp.reAttemptFactor = 0.5
simulProp.tmStpPrefactor = np.asarray([[0, 80000], [0.3, 1]]) # set up the time step prefactor
#simulProp.timeStepLimit = 0.5           # time step limit
simulProp.plotVar = ['w']              # plot fracture width and fracture front velocity
sim_name = "002_pc_2019-09-22__08_55_12"
simulProp.set_simulation_name(sim_name)
simulProp.solveStagnantTip = True
simulProp.saveRegime = True
simulProp.solveTipCorrRib = True
simulProp.elastohydrSolver = 'implicit_Anderson'
#simulProp.blockFigure = True
simulProp.saveToDisk = False

# initializing a static fracture
C = load_isotropic_elasticity_matrix(Mesh, Solid.Eprime)
Fr_geometry = Geometry('radial',radius=0.031)
init_param = InitializationParameters(Fr_geometry,
                                      #time=0.05,
                                      net_pressure=1.01e5,
                                      regime='M',
                                      elasticity_matrix=C)

Fr = Fracture(Mesh,
              init_param,
              Solid,
              Fluid,
              Injection,
              simulProp)

# create a controller
controller = Controller(Fr,
                        Solid,
                        Fluid,
                        Injection,
                        simulProp)

start_time = time.time()
# run the simulation
controller.run()
print("--- %s seconds ---" % (time.time() - start_time))


###################
#plotting results #
###################

from visualization import *


# loading simulation results
evalPointy = 0.075
evalPointx = 0.0
time_srs = np.asarray([15,1e5,1e8, 1020951375,3212427434.647137])
time_srs = np.asarray([15,3212427434])
Fr_list, properties = load_fractures(address="./Data/neutral_buoyancy",
                                     sim_name=sim_name,
                                     time_srs=time_srs)
                                     #time_period=1e9)
time_srs = get_fracture_variable(Fr_list,
                                 variable='time')
# Fr_list2, properties2 = load_fractures(address="./Data/neutral_buoyancy",
#                                      sim_name="Taisne_014",
#                                      #time_srs=time_srs)
#                                      time_period=200)
# time_srs2 = get_fracture_variable(Fr_list,
#                                  variable='time')

# # plot slice
# ext_pnts = np.empty((2, 2), dtype=np.float64)
# Fig_WS = plot_fracture_list_slice(Fr_list,
#                                   variable='w',
#                                   point1=[-evalPointx,evalPointy],
#                                   point2=[evalPointx,evalPointy],
#                                   projection='2D',
#                                   plot_cell_center=True,
#                                   extreme_points=ext_pnts)

# plot footprint
Fig_FP = None
Fig_FP = plot_fracture_list(Fr_list,
                            variable='mesh',
                            projection='2D',
                            mat_properties=Solid,
                            backGround_param='confining stress')
plt_prop = PlotProperties(plot_FP_time=False)
Fig_FP = plot_fracture_list(Fr_list,
                            variable='footprint',
                            projection='2D',
                            fig=Fig_FP,
                            plot_prop=plt_prop)
# plt_prop = PlotProperties(plot_FP_time=False,
#                           line_color='red')
# Fig_FP = plot_fracture_list(Fr_list2,
#                             variable='footprint',
#                             projection='2D',
#                             fig=Fig_FP,
#                             plot_prop=plt_prop)

# # plot width in 3D
# plot_prop_magma=PlotProperties(color_map='jet', alpha=0.1)
# Fig_Fr = plot_fracture_list(Fr_list,
#                             variable='width',
#                             projection='3D',
#                             plot_prop=plot_prop_magma
#                             )
# Fig_Fr = plot_fracture_list(Fr_list,
#                             variable='footprint',
#                             projection='3D',
#                             fig=Fig_Fr)

# exporting array with widht and mesh
#write_fracture_variable_csv_file("./Data/neutral_buoyancy/Taisne_003__2019-09-30__15_30_31/width.csv",Fr_list,'w')
#write_fracture_variable_csv_file("./Data/neutral_buoyancy/Taisne_003__2019-09-30__15_30_31/time.csv",Fr_list,'time')
#write_fracture_mesh_csv_file("./Data/neutral_buoyancy/Taisne_003__2019-09-30__15_30_31/mesh.csv",mesh_list)

evaluation_point = [0.0,2500]

intercepts = get_front_intercepts(Fr_list,evaluation_point)
b_stable = intercepts[-1][3] - intercepts[-1][2]

print(b_stable)

plt.show(block=True)
#  set block=True and comment last 2 lines if you want to keep the window open
