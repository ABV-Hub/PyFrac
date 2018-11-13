# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Haseeb Zia on Thu Dec 22 11:51:00 2016.
Copyright (c) ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory, 2016-2017. All rights reserved.
See the LICENSE.TXT file for more details.
"""

# import
import numpy as np
import sys
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.colors import to_rgb
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
import mpl_toolkits.mplot3d.art3d as art3d
from src.Properties import PlotProperties
import matplotlib.path as mpath

from src.Visualization import zoom_factory, to_precision, text3d
from src.Symmetry import *

class CartesianMesh:
    """ Class defining a Cartesian Mesh.

        Instance variables:
            Lx,Ly (float)           -- length of the domain in x and y directions respectively. The rectangular domain
                                       have a total length of 2xLx in the x direction and 2xLy in the y direction if
                                       both the positive and negative halves are included.
            nx,ny (int)             -- number of elements in x and y directions respectively
            hx,hy (float)           -- grid spacing in x and y directions respectively
            VertexCoor  (ndarray)   -- [x,y] Coordinates of the vertices
            CenterCoor  (ndarray)   -- [x,y] coordinates of the center of the elements
            NumberOfElts (int)      -- total number of elements in the mesh
            EltArea (float)         -- area of each element
            Connectivity (ndarray)  -- connectivity array giving four vertices of an element in the following order
                                        3         2
                                        0         1
            NeiElements (ndarray)   -- Giving four neighbouring elements with the following order:[left,right,bottom,up]
            distCenter (ndarray)    -- the distance of the cells from the center
            CenterElts (ndarray)    -- the element(s) in the center (the cell with the injection point)
            
        Methods:
            __init__()      -- create a uniform Cartesian mesh centered  [-Lx,Lx]*[-Ly,Ly]
            remesh()        -- remesh the grid uniformly by increasing the domain lengths with the given factor in both
                               x and y directions
    """

    def __init__(self, Lx, Ly, nx, ny, symmetric=False):
        """ 
        Creates a uniform Cartesian mesh centered at zero and having the dimensions of [-Lx,Lx]*[-Ly,Ly]
        Arguments:
            nx,ny (int)     -- number of elements in x and y directions respectively
            Lx,Ly (float)   -- lengths in x and y directions respectively
        """

        self.Lx = Lx
        self.Ly = Ly

        # Check if the number of cells is odd to see if the origin would be at the mid point of a single cell
        if nx % 2 == 0:
            print("Number of elements in x-direction are even. Using " + repr(nx+1) + " elements to have origin at a "
                                                                                      "cell center...")
            self.nx = nx+1
        else:
            self.nx = nx

        if ny % 2 == 0:
            print("Number of elements in y-direction are even. Using " + repr(ny+1) + " elements to have origin at a "
                                                                                      "cell center...")
            self.ny = ny+1
        else:
            self.ny = ny


        self.hx = 2. * Lx / (self.nx - 1)
        self.hy = 2. * Ly / (self.ny - 1)

        x = np.linspace(-Lx - self.hx / 2., Lx + self.hx / 2., self.nx + 1)
        y = np.linspace(-Ly - self.hy / 2., Ly + self.hy / 2., self.ny + 1)

        xv, yv = np.meshgrid(x, y)  # coordinates of the vertex of each elements

        a = np.resize(xv, ((self.nx + 1) * (self.ny + 1), 1))
        b = np.resize(yv, ((self.nx + 1) * (self.ny + 1), 1))

        self.VertexCoor = np.reshape(np.stack((a, b), axis=-1), (len(a), 2))

        self.NumberOfElts = self.nx * self.ny
        self.EltArea = self.hx * self.hy

        # Connectivity array giving four vertices of an element in the following order
        #     3         2
        #     0   -     1
        conn = np.empty([self.NumberOfElts, 4], dtype=int)
        k = 0
        for j in range(0, self.ny):
            for i in range(0, self.nx):
                conn[k, 0] = (i + j * (self.nx + 1))
                conn[k, 1] = (i + 1) + j * (self.nx + 1)
                conn[k, 2] = i + 1 + (j + 1) * (self.nx + 1)
                conn[k, 3] = i + (j + 1) * (self.nx + 1)
                k = k + 1

        self.Connectivity = conn

        # coordinates of the center of the elements
        CoorMid = np.empty([self.NumberOfElts, 2], dtype=float)
        for e in range(0, self.NumberOfElts):
            t = np.reshape(self.VertexCoor[conn[e]], (4, 2))
            CoorMid[e] = np.mean(t, axis=0)
        self.CenterCoor = CoorMid

        self.distCenter = (CoorMid[:, 0] ** 2 + CoorMid[:, 1] ** 2) ** 0.5

        # Giving four neighbouring elements in the following order: [left,right,bottom,up]
        Nei = np.zeros((self.NumberOfElts, 4), int)
        for i in range(0, self.NumberOfElts):
            Nei[i, :] = np.asarray(self.Neighbors(i, self.nx, self.ny))
        self.NeiElements = Nei

        # the element in the center (used for fluid injection)
        (minx, miny) = (min(abs(self.CenterCoor[:, 0])), min(abs(self.CenterCoor[:, 1])))
        self.CenterElts = np.intersect1d(np.where(abs(self.CenterCoor[:, 0]) < self.hx/2),
                                         np.where(abs(self.CenterCoor[:, 1]) < self.hy/2))
        if self.CenterElts.size != 1:
            #todo
            raise ValueError("Mesh with no center element. To be looked into")

        if symmetric:
            self.corr = corresponding_elements_in_symmetric(self)
            self.symmetric_elmnts = get_symetric_elements(self, np.arange(self.NumberOfElts))
            self.all, self.elements, self.boundary_x, self.boundary_y = get_active_symmetric_elements(self)

            self.vol_weights = np.full((len(self.all), ), 4., dtype=np.float32)
            self.vol_weights[len(self.elements): -1] = 2.
            self.vol_weights[-1] = 1.


    # -----------------------------------------------------------------------------------------------------------------------

    def locate_element(self, x, y):
        """
        This function gives the cell containing the given coordinates
        Arguments:
            x (float)  -- the x coordinate of the given point
            y (float)  -- the y coordinate of the given point

        Returns:
            elt (int)  -- the element containing the given coordinates
        """
        elt = np.intersect1d(np.where(abs(self.CenterCoor[:, 0] - x) <= self.hx/2.+sys.float_info.epsilon)[0],
                           np.where(abs(self.CenterCoor[:, 1] - y) <= self.hy/2.+sys.float_info.epsilon)[0])
        if elt.size>1:
            print("two found")
            return elt[0]
        return elt

#-----------------------------------------------------------------------------------------------------------------------


    def Neighbors(self, elem, nx, ny):
        """
        Neighbouring elements of an element within the mesh . Boundary elements have themselves as neighbor
        Arguments:
            elem (int): element whose neighbor are to be found
            nx (int):   number of elements in x direction
            ny (int):   number of elements in y direction

        Returns:
            int:        left neighbour
            int:        right neighbour
            int:        bottom neighbour
            int:        top neighbour
        """

        j = elem // nx
        i = elem % nx

        if i == 0:
            left = elem
        else:
            left = j * nx + i - 1

        if i == nx - 1:
            right = elem
        else:
            right = j * nx + i + 1

        if j == 0:
            bottom = elem
        else:
            bottom = (j - 1) * nx + i

        if j == ny - 1:
            up = elem
        else:
            up = (j + 1) * nx + i

        return (left, right, bottom, up)

# ----------------------------------------------------------------------------------------------------------------------


    def plot(self, material_prop=None, backGround_param=None, fig=None, plot_prop=None):
        """
        This function plots the mesh. If the material properties is given, the cells will be color coded according to
        the parameter given by the backGround_param argument

        Arguments:
            material_prop (MaterialProperties)      -- a MaterialProperties class object
            backGround_param (string)               -- the cells of the grid will be color coded according to the value
                                                       of the parameter given by this argument
        Returns:
            fig (Figure)                            -- A Figure object to superimpose
        """

        if fig is None:
            fig, ax = plt.subplots()
        else:
            ax = fig.get_axes()[0]

        # set the four corners of the rectangular mesh
        ax.set_xlim([-self.Lx - self.hx / 2, self.Lx + self.hx / 2])
        ax.set_ylim([-self.Ly - self.hy / 2, self.Ly + self.hy / 2])

        # add rectangle for each cell
        patches = []
        for i in range(self.NumberOfElts):
            polygon = Polygon(np.reshape(self.VertexCoor[self.Connectivity[i], :], (4, 2)), True)
            patches.append(polygon)

        if plot_prop is None:
            plot_prop = PlotProperties()
            plot_prop.alpha = 0.65
            plot_prop.lineColor = '0.5'
            plot_prop.lineWidth = 0.5

        p = PatchCollection(patches,
                            cmap=plot_prop.colorMap,
                            alpha=plot_prop.alpha,
                            edgecolor=plot_prop.meshEdgeColor,
                            linewidth=plot_prop.lineWidth)

        # applying color according to the prescribed parameter
        if material_prop is not None and backGround_param is not None:
            min_value, max_value, parameter, colors = process_material_prop_for_display(material_prop,
                                                                                        backGround_param)
            # plotting color bar
            sm = plt.cm.ScalarMappable(cmap=plot_prop.colorMap,
                                       norm=plt.Normalize(vmin=min_value, vmax=max_value))
            sm._A = []
            clr_bar = plt.colorbar(sm, alpha=0.65)
            clr_bar.set_label(parameter)
        else:
            colors = np.full((self.NumberOfElts,), 0.5)

        p.set_array(np.array(colors))
        ax.add_collection(p)
        plt.axis('equal')

        return fig

    def plot_3D(self, material_prop=None, backGround_param=None, fig=None, plot_prop=None):

        if backGround_param is not None and material_prop is None:
            raise ValueError("Material properties are required to plot the background parameter.")
        if material_prop is not None and backGround_param is None:
            print("back ground parameter not provided. Plotting confining stress...")
            backGround_param = 'sigma0'

        if fig is None:
            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1, projection='3d')
            ax.set_xlim(-self.Lx * 1.2, self.Lx * 1.2)
            ax.set_ylim(-self.Ly * 1.2, self.Ly * 1.2)
            plt.gca().set_aspect('equal')
            scale = 1.1
            zoom_factory(ax, base_scale=scale)
        else:
            ax = fig.get_axes()[0]

        if plot_prop is None:
            plot_prop = PlotProperties()
        if plot_prop.textSize is None:
            plot_prop.textSize = max(self.Lx / 15, self.Ly / 15)

        print("Plotting mesh in 3D...")
        if material_prop is not None and backGround_param is not None:
            min_value, max_value, parameter, colors = process_material_prop_for_display(material_prop,
                                                                                        backGround_param)

        # add rectangle for each cell
        for i in range(self.NumberOfElts):
            rgb_col = to_rgb(plot_prop.meshColor)
            if backGround_param:
                face_color = (rgb_col[0] * colors[i], rgb_col[1] * colors[i], rgb_col[2] * colors[i], 0.5)
            else:
                face_color = (rgb_col[0], rgb_col[1], rgb_col[2], 0.5)

            rgb_col = to_rgb(plot_prop.meshEdgeColor)
            edge_color = (rgb_col[0], rgb_col[1], rgb_col[2], 0.2)
            cell = mpatches.Rectangle((self.CenterCoor[i, 0] - self.hx / 2,
                                       self.CenterCoor[i, 1] - self.hy / 2),
                                      self.hx,
                                      self.hy,
                                      ec=edge_color,
                                      fc=face_color)
            ax.add_patch(cell)
            art3d.pathpatch_2d_to_3d(cell)

        if backGround_param is not None and material_prop is not None:
            make_3D_colorbar(self, material_prop, backGround_param, ax, plot_prop)

        self.plot_scale_3d(ax, plot_prop)

        ax.grid(False)
        ax.set_frame_on(False)
        ax.set_axis_off()

        return fig

    def plot_scale_3d(self, ax, plot_prop):
        print("\tPlotting scale...")

        Path = mpath.Path

        rgb_col = to_rgb(plot_prop.meshLabelColor)
        edge_color = (rgb_col[0], rgb_col[1], rgb_col[2], 1.)

        codes = []
        verts = []
        verts_x = np.linspace(-self.Lx, self.Lx, 7)
        verts_y = np.linspace(-self.Ly, self.Ly, 7)
        tick_len = max(self.hx / 2, self.hy / 2)
        for i in range(7):
            codes.append(Path.MOVETO)
            elem = self.locate_element(verts_x[i], -self.Ly)
            verts.append((self.CenterCoor[elem, 0], -self.Ly - self.hy / 2))
            codes.append(Path.LINETO)
            verts.append((self.CenterCoor[elem, 0], -self.Ly + tick_len))
            x_val = to_precision(np.round(self.CenterCoor[elem, 0], 5), plot_prop.dispPrecision)
            text3d(ax,
                   (self.CenterCoor[elem, 0] - plot_prop.dispPrecision * plot_prop.textSize / 3,
                    -self.Ly - self.hy / 2 - plot_prop.textSize,
                    0),
                   x_val,
                   zdir="z",
                   size=plot_prop.textSize,
                   usetex=False,
                   ec="none",
                   fc=edge_color)

            codes.append(Path.MOVETO)
            elem = self.locate_element(-self.Lx, verts_y[i])
            verts.append((-self.Lx - self.hx / 2, self.CenterCoor[elem, 1]))
            codes.append(Path.LINETO)
            verts.append((-self.Lx + tick_len, self.CenterCoor[elem, 1]))
            y_val = to_precision(np.round(self.CenterCoor[elem, 1], 5), plot_prop.dispPrecision)
            text3d(ax,
                   (-self.Lx - self.hx / 2 - plot_prop.dispPrecision * plot_prop.textSize,
                    self.CenterCoor[elem, 1] - plot_prop.textSize / 2,
                    0),
                   y_val,
                   zdir="z",
                   size=plot_prop.textSize,
                   usetex=False,
                   ec="none",
                   fc=edge_color)

        print("\tAdding labels...")
        text3d(ax,
               (0.,
                -self.Ly - plot_prop.textSize * 3,
                0),
               'meters',
               zdir="z",
               size=plot_prop.textSize,
               usetex=False,
               ec="none",
               fc=edge_color)

        path = mpath.Path(verts, codes)
        patch = mpatches.PathPatch(path,
                                   lw=plot_prop.lineWidth,
                                   facecolor='none',
                                   edgecolor=edge_color)
        ax.add_patch(patch)
        art3d.pathpatch_2d_to_3d(patch)


    def identify_elements(self, elements, fig=None, plot_prop=None, plot_mesh=True):

        if fig is None:
            fig, ax = plt.subplots()
        else:
            ax = fig.get_axes()[0]

        if plot_prop is None:
            plot_prop = PlotProperties()

        if plot_mesh:
            self.plot(fig=fig)
        # add rectangle for each cell
        patches = []
        for i in elements:
            polygon = Polygon(np.reshape(self.VertexCoor[self.Connectivity[i], :], (4, 2)), True)
            patches.append(polygon)

        p = PatchCollection(patches,
                            cmap=plot_prop.colorMap,
                            edgecolor=plot_prop.lineColor,
                            linewidth=plot_prop.lineWidth,
                            facecolors='none')
        ax.add_collection(p)

        # print Element numbers on the plot for elements to be identified
        for i in range(len(elements)):
            ax.text(self.CenterCoor[elements[i], 0] - self.hx / 4, self.CenterCoor[elements[i], 1] -
                    self.hy / 4, repr(elements[i]), fontsize=plot_prop.textSize)

        return fig


def make_3D_colorbar(mesh, material_prop, backGround_param, ax, plot_prop):
    print("\tMaking colorbar...")

    min_value, max_value, parameter, colors = process_material_prop_for_display(material_prop,
                                                                                backGround_param)
    rgb_col_mesh = to_rgb(plot_prop.meshEdgeColor)
    edge_color = (rgb_col_mesh[0],
                  rgb_col_mesh[1],
                  rgb_col_mesh[2],
                  0.2)

    color_range = np.linspace(0, 1., 11)
    y = np.linspace(-mesh.Ly, mesh.Ly, 11)
    dy = y[1] - y[0]
    for i in range(11):
        rgb_col = to_rgb(plot_prop.meshColor)
        face_color = (rgb_col[0] * color_range[i],
                      rgb_col[1] * color_range[i],
                      rgb_col[2] * color_range[i],
                      0.5)
        cell = mpatches.Rectangle((mesh.Lx + 4 * mesh.hx,
                                   y[i]),
                                  2 * dy,
                                  dy,
                                  ec=edge_color,
                                  fc=face_color)
        ax.add_patch(cell)
        art3d.pathpatch_2d_to_3d(cell)

    rgb_col_txt = to_rgb(plot_prop.meshLabelColor)
    txt_color = (rgb_col_txt[0],
                 rgb_col_txt[1],
                 rgb_col_txt[2],
                 1.0)
    text3d(ax,
           (mesh.Lx + 4 * mesh.hx, y[9] + 3 * dy, 0),
           parameter,
           zdir="z",
           size=plot_prop.textSize,
           usetex=False,
           ec="none",
           fc=txt_color)
    y = [y[0], y[5], y[10]]
    values = np.linspace(min_value, max_value, 11)
    values = [values[0], values[5], values[10]]
    for i in range(3):
        disp_val = to_precision(values[i], plot_prop.dispPrecision)
        text3d(ax,
               (mesh.Lx + 4 * mesh.hx + 2 * dy, y[i] + dy / 2, 0),
               disp_val,
               zdir="z",
               size=plot_prop.textSize,
               usetex=False,
               ec="none",
               fc=txt_color)


def process_material_prop_for_display(material_prop, backGround_param):
    colors = np.full((len(material_prop.SigmaO),), 0.5)

    if backGround_param == 'sigma0':
        max_value = max(material_prop.SigmaO) / 1e6
        min_value = min(material_prop.SigmaO) / 1e6
        if max_value - min_value > 0:
            colors = (material_prop.SigmaO / 1e6 - min_value) / (max_value - min_value)
        parameter = "confining stress ($MPa$)"
    elif backGround_param == 'K1c':
        max_value = max(material_prop.K1c) / 1e6
        min_value = min(material_prop.K1c) / 1e6
        if max_value - min_value > 0:
            colors = (material_prop.K1c / 1e6 - min_value) / (max_value - min_value)
        parameter = "fracture toughness ($Mpa\sqrt{m}$)"
    elif backGround_param == 'Cl':
        max_value = max(material_prop.Cl)
        min_value = min(material_prop.Cl)
        if max_value - min_value > 0:
            colors = (material_prop.Cl - min_value) / (max_value - min_value)
        parameter = "Leak off coefficient"
    elif backGround_param is not None:
        raise ValueError("Back ground color identifier not supported!")

    return min_value, max_value, parameter, colors