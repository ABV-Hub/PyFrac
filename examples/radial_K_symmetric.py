# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Haseeb Zia on Fri June 16 17:49:21 2017.
Copyright (c) "ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory", 2016-2017. All rights
reserved. See the LICENSE.TXT file for more details.
"""

# imports
from src.Fracture import *
from src.Controller import *


# creating mesh
Mesh = CartesianMesh(0.3, 0.3, 151, 151, symmetric=True)

# solid properties
nu = 0.4                            # Poisson's ratio
youngs_mod = 3.3e10                 # Young's modulus
Eprime = youngs_mod / (1 - nu ** 2) # plain strain modulus
K_Ic = 1e6                          # fracture toughness

def K_Ic_func(x, y):

    if abs(y) > 24:
        return 1.25e6
    else:
        return 1e6

Solid = MaterialProperties(Mesh,
                           Eprime,
                           K_Ic,)
                           # K1c_func=K_Ic_func)

# injection parameters
Q0 = 0.001  # injection rate
Injection = InjectionProperties(Q0, Mesh)

# fluid properties
Fluid = FluidProperties(viscosity=1.1e-5)

# simulation properties
simulProp = SimulationParameters()
simulProp.FinalTime = 0.0065               # the time at which the simulation stops
# simulProp.set_tipAsymptote('K')         # the tip asymptote is evaluated with the toughness dominated assumption
simulProp.tolFractFront = 0.005
simulProp.set_volumeControl(True)
# simulProp.frontAdvancing = 'implicit'   # to set explicit front tracking
simulProp.outputTimePeriod = 1e-4       # to save after every time step
# simulProp.tmStpPrefactor = 0.5          # decrease the pre-factor due to explicit front tracking
simulProp.set_outputFolder(".\\Data\\K_radial_symmetric") # the disk address where the files are saved
# simulProp.plotFigure = True
simulProp.plotAnalytical = True
simulProp.analyticalSol = "K"
simulProp.symmetric = True
simulProp.bckColor = "K1c"
simulProp.verbosity = 2

# initializing fracture
initRad = 0.27
init_param = ("K", "length", initRad)

# creating fracture object
Fr = Fracture(Mesh,
              init_param,
              Solid,
              Fluid,
              Injection,
              simulProp)


# create a Controller
controller = Controller(Fr,
                        Solid,
                        Fluid,
                        Injection,
                        simulProp)

# run the simulation
controller.run()


# ####################
# # plotting results #
# ####################
#
# # loading simulation results
# Fr_list, properties = load_fractures(address=".\\Data\\K_radial_symmetric")       # load all fractures
# time_srs = get_fracture_variable(Fr_list,                                        # list of times
#                                  variable='time')
#
# plot_prop = PlotProperties()
#
# # plot fracture radius
# plot_prop.lineStyle = '.'
# plot_prop.graphScaling = 'loglog'
# Fig_R = plot_fracture_list(Fr_list,
#                            variable='d_mean',
#                            plot_prop=plot_prop)
# # plot analytical radius
# Fig_R = plot_analytical_solution('K',
#                                  'd_mean',
#                                  Solid,
#                                  Injection,
#                                  fluid_prop=Fluid,
#                                  time_srs=time_srs,
#                                  fig=Fig_R)
#
# Fig_eff = plot_fracture_list(Fr_list,
#                            variable='ef',
#                            plot_prop=plot_prop)
#
# # plot width at center
# Fig_w = plot_fracture_list_at_point(Fr_list,
#                                     variable='w',
#                                     plot_prop=plot_prop)
# # plot analytical width at center
# Fig_w = plot_analytical_solution_at_point('K',
#                                           'w',
#                                           Solid,
#                                           Injection,
#                                           fluid_prop=Fluid,
#                                           time_srs=time_srs,
#                                           fig=Fig_w)
#
# time_srs = np.linspace(1, 1e5, 10)
# Fr_list, properties = load_fractures(address=".\\Data\\K_radial_symmetric",
#                                      time_srs=time_srs)
# time_srs = get_fracture_variable(Fr_list,
#                                  variable='time')
#
# # plot footprint
# Fig_FP = plot_fracture_list(Fr_list,
#                             variable='mesh',
#                             projection='2D')
# Fig_FP = plot_fracture_list(Fr_list,
#                             variable='footprint',
#                             projection='2D',
#                             fig=Fig_FP)
# # plot analytical footprint
# Fig_FP = plot_analytical_solution('K',
#                                   'footprint',
#                                   Solid,
#                                   Injection,
#                                   fluid_prop=Fluid,
#                                   time_srs=time_srs,
#                                   projection='2D',
#                                   fig=Fig_FP)
#
#
# # plot slice
# pnt_1=[-Fr_list[-1].mesh.Lx, 0]
# pnt_2=[Fr_list[-1].mesh.Lx, 0]
# Fig_WS = plot_fracture_list_slice(Fr_list,
#                                   variable='w',
#                                   projection='2D',
#                                   point1=pnt_1,
#                                   point2=pnt_2)
# #plot slice analytical
# Fig_WS = plot_analytical_solution_slice('K',
#                                         'w',
#                                         Solid,
#                                         Injection,
#                                         fluid_prop=Fluid,
#                                         fig=Fig_WS,
#                                         time_srs=time_srs,
#                                         plt_2D_image=False,
#                                         point1=pnt_1,
#                                         point2=pnt_2)
#
#
# plt.show()

