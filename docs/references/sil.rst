Software-in-the-loop
--------------------
The `sil_example <https://github.com/dos-group/vessim/blob/main/examples/sil_example.py>`_ is a co-simulation example with software-in-the-loop. 
This scenario builds on `cosim_example <https://github.com/dos-group/vessim/blob/main/examples/cosim_example.py>`_ but connects to a real computing system through software-in-the-loop integration. 
This example is experimental and documentation is still in progress.

Install vessim with the software-in-the-loop dependencies

.. code-block:: console

    pip install vessim[sil]

and run

.. code-block:: console 

    python examples/sil_example.py