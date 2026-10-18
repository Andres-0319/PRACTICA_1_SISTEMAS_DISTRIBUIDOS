<div align="center">

# Universidad Politécnica Salesiana

# Carrera de Computación

# Asignatura de Sistemas Distribuidos

</div>

**Integrantes:** Burgos Andrés, Morales Pool, Narváez Cristian

**Fecha:** 22 de octubre de 2026

**Tema:** Taller Grupal Sockets Multihilo

**Objetivo**

Evolucionar el código base del servidor de eco y cliente actual hacia un sistema de chat en red LAN totalmente funcional, donde múltiples clientes puedan conectarse simultáneamente, enviar mensajes de texto y ver en tiempo real lo que escriben los demás participantes, utilizando exclusivamente la consola de comandos.

**Desarrollo de la actividad**

**Paso 1:** Configurar y preparar adecuadamente el entorno virtual de trabajo dentro del sistema operativo Linux Ubuntu, para luego proceder con la ejecución del script principal del servidor utilizando el lenguaje de programación Python en la consola correspondiente. Esta acción permitirá inicializar el proceso de escucha activa en la red local a través del uso de sockets orientados a conexión bajo el protocolo TCP, y hará que el servidor se vincule de forma correcta a todas las interfaces disponibles especificando la dirección IP genérica y asignando el puerto de red definido.

<img width="652" height="134" alt="image" src="https://github.com/user-attachments/assets/d7b7004e-6dce-45b2-b38f-706c772fec38" />

**Paso 2:** Una vez que el servidor se encuentre ejecutándose y escuchando activamente, se ejecuta el procedimiento que consiste en validar las conexiones entrantes en la que se podrá monitorear en tiempo real cada uno de los eventos de red generados por los usuarios a través de la consola del servidor principal. El sistema registrará de manera automática y secuencial las direcciones IP junto con los puertos dinámicos utilizados por cada máquina cliente; cada evento queda debidamente documentado con su respectiva marca de tiempo, permitiendo comprobar la estabilidad del sistema multihilo implementado.

<img width="886" height="140" alt="image" src="https://github.com/user-attachments/assets/515b0495-de80-4824-84a7-84b8f40cb4b1" />

**Paso 3:** Para dar inicio a la interacción comunicativa desde la perspectiva del usuario, el primer cliente accede a su terminal y activa su entorno virtual local, ejecutando el script del cliente mediante el comando de Python para establecer un canal de comunicación directo con la dirección del servidor correspondiente. Una vez que se haya ingresado los datos requeridos por el sistema, se inicia con éxito la sesión correspondiente mostrando un mensaje de confirmación de conexión en la consola del usuario evidenciándose el intercambio de mensajes de prueba enviados y la recepción sincronizada de las notificaciones del sistema del chat. 

<img width="655" height="483" alt="image" src="https://github.com/user-attachments/assets/b01aea65-3fdf-4b8b-a7d4-d176700d595e" />

**Paso 4:** Para completar satisfactoriamente el escenario de pruebas del sistema distribuido multihilo, el segundo usuario procederá a replicar los pasos de inicialización mencionados anteriormente. Desde la otra máquina dentro de la misma red local, se activa el entorno de trabajo y se ejecuta el script del cliente correspondiente, permitiendo apreciar como el sistema notifica de inmediato la incorporación del nuevo participante a todos los usuarios conectados. Cuando ambos clientes ejecutan los respectivos archivos de Python, ambos podrán intercambiar mensajes en tiempo real validando la funcionalidad del broadcast implementada en la arquitectura del servidor.

<img width="907" height="585" alt="image" src="https://github.com/user-attachments/assets/e010b15e-3ed0-4830-8316-aff22d9078ac" />

**Paso 5:** Para validar el comportamiento del sistema ante la desconexión voluntaria del usuario correspondiente, se realizaron pruebas adicionales ejecutando el servidor de forma local. En la evidencia visual, se observa la interacción del usuario 1 (Pool Morales), quien se encarga de establecer una conexión mediante la interfaz del bucle localhost; y también se observa el ingreso del usuario 2 (Jose), probando el envío de mensajes de texto y comandos de control interactivo, en donde el usuario evalúa diferentes alternativas para abandonar la sesión actual introduciendo comandos como "/salir".

<img width="1128" height="583" alt="image" src="https://github.com/user-attachments/assets/25f1cd72-14a8-4c3d-a2d2-e6936aa3e819" />

**Paso 6:** Como parte final del proceso de depuración y validación del código correspondiente, se llevó a cabo una verificación integral del entorno de desarrollo de VS Code. En su interfaz gráfica, se muestra el editor con el script principal del servidor destacando las funciones lógicas encargadas de la codificación y la recepción de mensajes, mostrándose una ejecución exitosa del archivo "server.py" que se encarga de escuchar activamente la dirección IP local estipulada desde el inicio de las pruebas correspondientes.

<img width="955" height="972" alt="image" src="https://github.com/user-attachments/assets/d10e9e1c-1de4-4584-88dc-521174596b3e" />

**Paso 7:**

**Conclusiones**

- El uso de sockets multihilo en combinación con la gestión de hilos independientes permitió la construcción de un servidor y cliente concurrentes capaces de procesar mensajes en tiempo real sin interrupciones en la interfaz de comandos.
- La correcta elaboración del código bajo principios de diseño y un robusto manejo de excepciones garantizó la estabilidad del sistema ante la conexión y desconexión simultánea de múltiples usuarios en la red LAN.
