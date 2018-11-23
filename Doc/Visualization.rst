

Post-processing and Visualization
=================================

A comprehensive set of post-processing and visualization routines are provided by **PyFrac**. The fist step to visualize the results is to load the fracture objects at different times from a stored simulation run. :py:func:`PostProcessFracture.load_fractures` function will do that for you. You can provide the time series at which the fractures are to be loaded. The function will provide a list of Fracture objects with the closest times to the given time series. Note that for a time given in the time series, the fracture with time closest and larger to it will be returned. Let us load a fracture at the simulation time of 100 seconds from the results of the simulation run in the :ref:`run-a-simulation` chapter.

.. code-block:: python

    from src.PostProcessFracture import *
    Fr_list = load_fractures(sim_name='radial', time_srs=[100])

The above instruction will return a list of :py:class:`Fracture` objects corresponding to the given time series, which is of length one in this case. Note that since we have not provided any folder address, the results will be loaded from the default folder. Also, if multiple simulations with the same simulation name are found, the most recent run will be loaded. To visualize the fracture, we can use the :py:func:`Fracture.plot_fracture` function.

.. code-block:: python

    Fr_list[0].plot_fracture()

With the default options, this function plots the mesh, the footprint and the fracture width with 3D projection. The 3D plot is interactive and can be zoomed in using the mouse wheel.

.. image:: /images/default_fracture.png
    :align:   center
    :scale: 80 %

You can also provide which quantity you want to plot. The following quantities can be plotted.

.. csv-table:: supported variables
    :align:   center
    :header: "supported variables"

    'w' or 'width'
    'p' or 'pressure'
    'v' or 'front velocity'
    'Re' or 'Reynolds number'
    'ff' or 'fluid flux'
    'fv' or 'fluid velocity'
    'mesh'
    'footprint'
    'lk' or 'leaked off'

.. note:: The variables 'Reynolds number', 'fluid flux' and 'fluid velocity' are not saved by default in the results. Their saving can be enabled using simulation properties. See :py:class:`Properties.SimulationProperties` for details.

For example, to plot fracture footprint in 2D projection, we can do the following:

.. code-block:: python

    Fig = Fr_list[0].plot_fracture(variable='mesh', projection='2D')
    Fig = Fr_list[0].plot_fracture(variable='footprint', fig=Fig, projection='2D')

The first instruction will plot mesh of the Fracture and will return a :py:class:`Figure` object. We can use the same figure to plot the footprint. In this case, it will be superimposed on the first plot. The above example shows only some basic functionality. For a complete list of available options, see the documentation of the :py:func:`Fracture.plot_fracture` function.

Apart from plotting the whole fracture, you can also plot a slice of the fracture using the py:func:`Fracture.plot_fracture_slice` function. You can give any two points on the domain and the function will plot fracture slice on the mesh joining the two points. let us plot a slice of our mesh passing from the two points (-7, -5) and (7, 5).

.. code-block:: python

    Fr_list[0].plot_fracture_slice(variable='width', point1=[-7, -5], point2=[7, 5])

By default, it will be plotted in 2D projection, but 3D projection can also be plotted.

.. image:: /images/fracture_slice.png
    :align:   center
    :scale: 80 %

