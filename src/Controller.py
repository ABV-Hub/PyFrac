
# from src.Fracture import Fracture
from src.Properties import *
from src.Elasticity import *
from src.HFAnalyticalSolutions import *
from src.TimeSteppingVolumeControl import attempt_time_step_volumeControl
from src.TimeSteppingViscousFluid import attempt_time_step_viscousFluid
from src.TimeSteppingMechLoading import attempt_time_step_mechLoading

import copy
import matplotlib.pyplot as plt

class Controller:

    errorMessages = ("Propagation not attempted",
                     "Time step successful",
                     "Evaluated level set is not valid",
                     "Front is not tracked correctly",
                     "Evaluated tip volume is not valid",
                     "Solution obtained from the elastohydrodynamic solver is not valid",
                     "Did not converge after max iterations",
                     "Tip inversion is not correct",
                     "Ribbon element not found in the enclosure of the tip cell",
                     "Filling fraction not correct",
                     "Toughness iteration did not converge",
                     "projection could not be found",
                     "Reached end of grid"
                     )


    def __init__(self, Fracture=None, Solid_prop=None, Fluid_prop=None, Injection_prop=None, Sim_prop=None,
                 Load_prop=None, C=None):

       self.fracture = Fracture
       self.solid_prop = Solid_prop
       self.fluid_prop = Fluid_prop
       self.injection_prop = Injection_prop
       self.sim_prop = Sim_prop
       self.load_prop = Load_prop
       self.C = C
       self.fr_queue = [None, None, None, None, None]
       self.smallStep_cnt = 0

    def run(self):
        # load elasticity matrix
        if self.C is None:
            self.C = load_elasticity_matrix(self.fracture.mesh, self.solid_prop.Eprime)


        # starting time stepping loop
        i = 0
        Fr = self.fracture
        tmSrs_indx = 0
        next_in_tmSrs = self.sim_prop.solTimeSeries[tmSrs_indx]
        if next_in_tmSrs < Fr.time:
            raise SystemExit('The minimum time required in the given time series or the end time'
                             ' is less than initial time.')

        while (Fr.time < self.sim_prop.FinalTime) and (i < self.sim_prop.maxTimeSteps):

            # time step is calculated with the current propagation velocity
            TimeStep = self.sim_prop.tmStpPrefactor * min(Fr.mesh.hx, Fr.mesh.hy) / np.max(Fr.v)

            # to get the solution at the times given in time series
            if Fr.time + TimeStep > next_in_tmSrs:
                TimeStep = next_in_tmSrs - Fr.time
                if tmSrs_indx < len(self.sim_prop.solTimeSeries)-1:
                    tmSrs_indx += 1
                next_in_tmSrs = self.sim_prop.solTimeSeries[tmSrs_indx]

            status, Fr_n_pls1 = self.advance_time_step(Fr,
                                                 self.C,
                                                 TimeStep)

            if status == 1:
                Fr = copy.deepcopy(Fr_n_pls1)
                self.fr_queue[i%5] = copy.deepcopy(Fr_n_pls1)
                self.smallStep_cnt += 1
                if self.smallStep_cnt%4 == 0:
                    self.sim_prop.tmStpPrefactor = self.sim_prop.tmStpPrefactor_max
            elif status == 12:
                self.C *= 1/2.
                Fr = Fr.remesh(2., self.C, self.solid_prop, self.fluid_prop, self.injection_prop, self.sim_prop)

            else:
                print("Restarting with the last check point...")
                self.sim_prop.tmStpPrefactor *= 0.8
                self.smallStep_cnt = 0
                if self.fr_queue[(i+1) % 5 ] == None or self.sim_prop.tmStpPrefactor < 0.1:
                    raise SystemExit("Simulation failed.")
                else:
                    Fr = copy.deepcopy(self.fr_queue[(i+1) % 5])

            i = i + 1

        print("\n\n-----Simulation successfully finished------")
        print("Final time = " + repr(Fr.time))


#-----------------------------------------------------------------------------------------------------------------------


    def advance_time_step(self, Frac, C, TimeStep):
        """
        This function advances the fracture by the given time step. In case of failure, reattempts are made with smaller
        time steps. A system exit is raised after maximum allowed reattempts.

        Arguments:
            Frac (Fracture object):                                 fracture object from the last time step
            C (ndarray-float):                                      the elasticity matrix


            TimeStep (float):                                       time step to be attempted

            Loading_Properties (LoadingProperties object)


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

            Fracture object:            fracture after advancing time step.
        """
        print('\n--------------------------------\ntime = ' + repr(Frac.time))

        if TimeStep > self.sim_prop.timeStep_limit:
            TimeStep = self.sim_prop.timeStep_limit
            self.sim_prop.timeStep_limit = TimeStep * 1.8

        if TimeStep < 0:
            TimeStep = self.sim_prop.timeStep_limit*2

        # loop for reattempting time stepping in case of failure.
        for i in range(0, self.sim_prop.maxReattempts):
            # smaller time step to reattempt time stepping; equal to the given time step on first iteration
            smallerTimeStep = TimeStep * self.sim_prop.reAttemptFactor ** i

            if i > self.sim_prop.maxReattempts/2-1:
                smallerTimeStep = TimeStep * (1/self.sim_prop.reAttemptFactor)**(i+1 - self.sim_prop.maxReattempts/2)

            print("Attempting time step of " + repr(smallerTimeStep) + " sec...")

            if self.sim_prop.viscousInjection:
                status, Fr = attempt_time_step_viscousFluid(Frac,
                                                            C,
                                                            self.solid_prop,
                                                            self.fluid_prop,
                                                            self.sim_prop,
                                                            self.injection_prop,
                                                            smallerTimeStep)

            elif self.sim_prop.dryCrack_mechLoading:
                status, Fr = attempt_time_step_mechLoading(Frac,
                                                           C,
                                                           self.solid_prop,
                                                           self.sim_prop,
                                                           self.load_prop,
                                                           smallerTimeStep,
                                                           Frac.mesh)

            elif self.sim_prop.volumeControl:
                status, Fr = attempt_time_step_volumeControl(Frac,
                                                             C,
                                                             self.solid_prop,
                                                             self.sim_prop,
                                                             self.injection_prop,
                                                             smallerTimeStep,
                                                             Frac.mesh)
            if status == 1:
                print(self.errorMessages[status])

                # output
                if self.sim_prop.plotFigure or self.sim_prop.saveToDisk:
                    self.output(Frac,
                           Fr,
                           self.sim_prop,
                           self.solid_prop,
                           self.injection_prop,
                           self.fluid_prop)

                return status, Fr
            else:
                print(self.errorMessages[status])
                if status == 12:
                    return status, Fr
            print("Time step failed...")

        return status, Fr



    #-------------------------------------------------------------------------------------------------------------------

    def output(self, Fr_lstTmStp, Fr_advanced, simulation_parameters, material_properties, injection_parameters,
               fluid_properties):
        """
        This function plot the fracture footprint and/or save file to disk according to the given time period.

        Arguments:
            Fr_lstTmStp (Fracture object):                      fracture from last time step
            Fr_advanced (Fracture object):                      fracture after time step advancing
            simulation_parameters (SimulationParameters object): simulation parameters
            material_properties (MaterialProperties object):    Material properties

        Returns:
        """
        if (Fr_lstTmStp.time // simulation_parameters.outputTimePeriod !=
                    Fr_advanced.time // simulation_parameters.outputTimePeriod):
            # plot fracture footprint
            if simulation_parameters.plotFigure:
                # if ploting analytical solution enabled
                if simulation_parameters.plotAnalytical:
                    Q0 = injection_parameters.injectionRate[1, 0]  # injection rate at the start of injection
                    if simulation_parameters.analyticalSol in ('M', 'Mt', 'K', 'Kt', 'E'): #radial fracture
                        t, R, p, w, v, actvElts = HF_analytical_sol(simulation_parameters.analyticalSol,
                                                                    Fr_lstTmStp.mesh,
                                                                    material_properties.Eprime,
                                                                    Q0,
                                                                    muPrime=fluid_properties.muPrime,
                                                                    Kprime=material_properties.Kprime[
                                                                        Fr_lstTmStp.mesh.CenterElts],
                                                                    Cprime=material_properties.Cprime[
                                                                        Fr_lstTmStp.mesh.CenterElts],
                                                                    t=Fr_advanced.time,
                                                                    KIc_min=material_properties.K1c_perp)
                    elif simulation_parameters.analyticalSol == 'PKN':
                        print("PKN is to be implemented.")

                    Fr_advanced.plot_fracture(analytical=R,
                                                mat_properties=material_properties,
                                                sim_properties=simulation_parameters)
                else:
                    Fr_advanced.plot_fracture(mat_properties=material_properties,
                                                sim_properties=simulation_parameters)
                plt.show()

            # save fracture to disk
            if simulation_parameters.saveToDisk:
                simulation_parameters.lastSavedFile += 1
                Fr_advanced.SaveFracture(simulation_parameters.outFileAddress + "file_"
                                         + repr(simulation_parameters.lastSavedFile))