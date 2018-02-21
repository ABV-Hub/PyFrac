# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Haseeb Zia on Fri June 16 17:49:21 2017.
Copyright (c) "ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory", 2016-2017. All rights reserved.
See the LICENSE.TXT file for more details.
"""

# imports
from src.Fracture import *
from src.Controller import *
from src.PostProcess import *

# creating mesh
Mesh = CartesianMesh(12, 12, 51, 51)

# solid properties
nu = 0.4                            # Poisson's ratio
youngs_mod = 3.3e10                 # Young's modulus
Eprime = youngs_mod / (1 - nu ** 2) # plain strain modulus
K_Ic = np.full((Mesh.NumberOfElts,), 2e6, dtype=np.float64)

def sigmaO_func(x, y):
    """ The function providing the confining stress"""

    if y > 5:
        return 4.e6
    elif y < -2.5:
        return 0.5e6
    else:
        return 1.5e6

Solid = MaterialProperties(Mesh,
                           Eprime,
                           K_Ic,
                           SigmaO_func=sigmaO_func)

# injection parameters
Q0 = 0.001  # injection rate
Injection = InjectionProperties(Q0, Mesh)

# fluid properties
Fluid = FluidProperties(viscosity=1.1e-3)

# simulation properties
simulProp = SimulationParameters()
simulProp.plotFigure = False            # to disable plotting of figures while the simulation runs
simulProp.saveToDisk = True             # to enable saving the results (to hard disk)
simulProp.set_outFileAddress(".\\Data\\stress_contrast") # the disk address where the files are saved
simulProp.outputTimePeriod = 0.1        # the time after which the file is saved
simulProp.bckColor = 'sigma0'           # the parameter according to which the background is color coded
simulProp.FinalTime = 150.              # the time to stop the simulation


# initializing fracture
initRad = 2.0
init_param = ('M', "length", initRad)

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
animate_simulation_results(simulProp.get_outFileAddress(),
               time_period=1.0)
plot_footprint_3d(simulProp.get_outFileAddress(),
                time_period=25.0,
                plt_mesh=True)
plt.show()
