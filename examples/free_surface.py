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
Mesh = CartesianMesh(1, 1, 3, 3)

# solid properties
nu = 0.4                            # Poisson's ratio
youngs_mod = 3.3e10                 # Young's modulus
Eprime = youngs_mod / (1 - nu ** 2) # plain strain modulus
K_Ic = 1.8e6

def sigmaO_func(x, y):
    """ The function providing the confining stress"""
    if y > 5:
        return 2.e6
    elif y < -2.5:
        return 1.2e6
    else:
        return 1.7e6

Cij = get_Cij_Matrix(youngs_mod, nu)
Solid = MaterialProperties(Mesh,
                           Eprime,
                           K_Ic,
                           SigmaO_func=sigmaO_func,
                           free_surf=False,
                           # TI_elasticity=True,
                           Cij=Cij,
                           free_surf_depth=3.)

# injection parameters
Q0 = 0.001  # injection rate
Injection = InjectionProperties(Q0, Mesh)

# fluid properties
Fluid = FluidProperties(viscosity=1.2e-3)

# simulation properties
simulProp = SimulationParameters()
simulProp.outputTimePeriod = 0.1        # Setting it small so the file is saved after every time step
simulProp.bckColor = 'sigma0'           # the parameter according to which the background is color coded
simulProp.FinalTime = 190.              # the time to stop the simulation
simulProp.TI_KernelExecPath = 'C:\\Users\\Haseeb\\Documents\\GitHubPyFrac\\src_TI_Kernel\\Debug\\'
simulProp.verbosity = 2
simulProp.plotFigure = True

C1 = load_isotropic_elasticity_matrix(Mesh, Eprime)
C2 = load_TI_elasticity_matrix(Mesh, Solid, simulProp)

print(repr(sum(sum(1. - C1/C2))))
plt.imshow(C1/C2)
# plt.figure(2)
# plt.imshow(C1)
plt.show()
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
#
# plot results
animate_simulation_results(simulProp.get_outFileAddress(),
                    time_period=5.0)

plot_times = np.array([2, 15, 40, 95, 180])
plot_footprint_3d(simulProp.get_outFileAddress(),
                    plot_at_times=plot_times,
                    txt_size=2.)    # the size of the text displaying the time and the length of the fracture
plt.show()
