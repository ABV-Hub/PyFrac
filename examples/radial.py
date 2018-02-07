# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Haseeb Zia on Fri June 16 17:49:21 2017.
Copyright (c) "ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory", 2016-2017. All rights reserved.
See the LICENSE.TXT file for more details.
"""


# adding src folder to the path
# import sys
# if "win32" in sys.platform or "win64" in sys.platform:
#     slash = "\\"
# else:
#     slash = "/"
# if not '..' + slash + 'src' in sys.path:
#     sys.path.append('..' + slash + 'src')
# if not '.' + slash + 'src' in sys.path:
#     sys.path.append('.' + slash + 'src')

# imports
from src.Fracture import *
from src.Controller import *
from src.PostProcess import plot_simulation_results

# creating mesh
Mesh = CartesianMesh(30, 30, 41, 41)

# solid properties
nu = 0.4                            # Poisson's ratio
youngs_mod = 3.3e10                 # Young's modulus
Eprime = youngs_mod / (1 - nu ** 2) # plain strain modulus
K_Ic = 5e6                          # fracture toughness

Solid = MaterialProperties(Mesh,
                           Eprime,
                           K_Ic)

# injection parameters
Q0 = 0.001  # injection rate
Injection = InjectionProperties(Q0, Mesh)

# fluid properties
Fluid = FluidProperties()

# simulation properties
simulProp = SimulationParameters()
simulProp.FinalTime = 1e9               # the time at which the simulation stops
simulProp.plotFigure = False            # to disable plotting of figures while the simulation runs
simulProp.saveToDisk = True             # to enable saving the results (to hard disk)
simulProp.set_outFileAddress(".\\Data\\radial") # the disk address where the files are saved
simulProp.set_volumeControl(True)       # to set up the solver in volume control mode (inviscid fluid)
simulProp.set_tipAsymptote('K')         # the tip asymptote is evaluated with the toughness dominated assumption


# initializing fracture
initRad = 10.
init_param = ("K", "l", initRad)

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

# plot results
plot_simulation_results(simulProp.get_outFileAddress(),         # the address where the results are stored
                        sol_t_srs=simulProp.get_solTimeSeries(),# the time series at which the solution is plotted
                        analytical_sol='K')                     # analytical solution for reference

