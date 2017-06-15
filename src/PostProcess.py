#
# This file is part of PyFrac.
#
# Created by Brice Lecampion on 12.06.17.
# Copyright (c) ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory, 2016-2017.  All rights reserved.
# See the LICENSE.TXT file for more details. 
#
#
# post-process script from reading files  in simulation folder.....

# adding src folder to the path
import sys
if "wind" in sys.platform:
    slash = "\\"
else:
    slash = "/"
if not '..' + slash + 'src' in sys.path:
    sys.path.append('.' + slash + 'src')
if not '.' + slash + 'src' in sys.path:
    sys.path.append('.' + slash + 'src')

# imports
import numpy as np
from src.CartesianMesh import *
from src.Fracture import *
from src.Properties import *

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from matplotlib.animation import FuncAnimation




def animate_simulation_results(address, time_period= 0.0, colormap=cm.jet, edge_color = 'None', Interval=400,
                               Repeat=None, maxFiles=1000 ):
    """
    This function plays an animation of the evolution of fracture with time. See the arguments list for options

    Arguments:
        address (string):               the folder containing the fracture files
        time_period (float):            the output time period after which the next available fracture will be plotted.
                                        This is the minimum time between two ploted fractures and can be used to avoid
                                        clutter.
        colormap (matplotlib colormap): the color map used to plot
        edge_color (matplotlib colors): the color used to plot the grid lines
        Interval (float):               time in milliseconds between the frames of animation
        Repeat (boolean):               True will play the animation in a loop
        maxFiles (int):                 the maximum no. of files to be loaded

    """

    if "win32" in sys.platform or "win64" in sys.platform:
        slash = "\\"
    else:
        slash = "/"
    if not '..' + slash + 'src' in sys.path:
        sys.path.append('.' + slash + 'src')
    if not '.' + slash + 'src' in sys.path:
        sys.path.append('.' + slash + 'src')

    # read properties
    filename = address + slash + "properties"
    try:
        with open(filename, 'rb') as input:
            (Solid, Fluid, Injection, SimulProp) = pickle.load(input)
    except FileNotFoundError:
        raise SystemExit("Properties file not found.")


    fileNo = 0
    fraclist = [];
    nxt_plt_t = 0.0
    while fileNo < maxFiles:

        # trying to load next file. exit loop if not found
        try:
            ff = ReadFracture(address + slash + "file_" + repr(fileNo))
        except FileNotFoundError:
            break
        fileNo+=1

        if ff.time >= nxt_plt_t:
            # if the current fracture time has advanced the output time period
            fraclist.append(ff)
            nxt_plt_t = ff.time + time_period

    #todo mesh seperate from fracture
    Mesh = ff.mesh   # because Mesh is not stored in a separate file for now

    fig, ax = plt.subplots()
    ax.set_xlim([-Mesh.Lx, Mesh.Lx])
    ax.set_ylim([-Mesh.Ly, Mesh.Ly])

    # make grid cells
    patches = []
    for i in range(Mesh.NumberOfElts):
        polygon = Polygon(np.reshape(Mesh.VertexCoor[Mesh.Connectivity[i], :], (4, 2)), True)
        patches.append(polygon)

    p = PatchCollection(patches, cmap=colormap, alpha=0.7, edgecolor=edge_color)

    # applying different colors for different types of elements
    # todo needs to be done properly
    colors = 100. * np.full(len(patches), 0.9)
    colors += -100. * (Solid.SigmaO) / np.max(Solid.SigmaO)
    colors += -100. * (Solid.Kprime) / np.max(Solid.Kprime)

    p.set_array(np.array(colors))
    ax.add_collection(p)



    args = (fraclist, fileNo)
    # animate fracture
    animation = FuncAnimation(fig, update, fargs=args, frames=len(fraclist), interval=Interval, repeat=Repeat)  # ,extra_args=['-vcodec', 'libxvid']
    plt.show()
    # animation.save(address + slash +'Footprint-evol.mp4', metadata={'copyright':'EPFL - GeoEnergy Lab'})


def update(frame, *args):
    """
    This function update the frames to be used in the animation.

    """

    # loading the fracture list
    (fraclist, noFractures) = args

    ffi = fraclist[frame]

    I =ffi.Ffront[:,0:2]
    J= ffi.Ffront[:,2:4]

    for e in range(0,len(I)):
        plt.plot(np.array([I[e, 0], J[e, 0]]), np.array([I[e, 1], J[e, 1]]), '-k')

    plt.title('Time ='+ "%.4f" % ffi.time+ ' sec.')
    plt.axis('equal')



