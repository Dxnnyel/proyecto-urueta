from django.db import models
from django.utils import timezone
import random
import string
from django.contrib.auth.models import User

def _generar_codigo():
    return ''.join(random.choices(string.digits, k=6))


class CodigoVerificacion(models.Model):
    username  = models.CharField(max_length=150)
    email     = models.EmailField()
    password  = models.CharField(max_length=256)
    codigo    = models.CharField(max_length=6, default=_generar_codigo)
    creado_el = models.DateTimeField(auto_now_add=True)
    intentos  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Código de verificación'
        verbose_name_plural = 'Códigos de verificación'

    def esta_expirado(self):
        return timezone.now() > self.creado_el + timezone.timedelta(minutes=15)

    def __str__(self):
        return f'{self.email} — {self.codigo}'


class Producto(models.Model):
    nombre      = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    cantidad    = models.PositiveIntegerField(default=0)
    precio      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    creado_el   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'producto'
        verbose_name_plural = 'productos'
        ordering            = ['-creado_el']

    def __str__(self):
        return self.nombre


class Vehiculo(models.Model):
    TIPO_TRABAJO = [
        ('mecanica',  'Mecánica'),
        ('electrico', 'Eléctrico'),
        ('aire',      'Aire acondicionado'),
        ('latoneria', 'Latonería'),
        ('pintura',   'Pintura'),
    ]

    placa         = models.CharField(max_length=10)
    fecha_entrada = models.DateField(auto_now_add=True)
    fecha_salida  = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    trabajo       = models.CharField(max_length=20, choices=TIPO_TRABAJO)
    responsable   = models.CharField(max_length=100)

    class Meta:
        verbose_name        = 'vehículo'
        verbose_name_plural = 'vehículos'
        ordering            = ['-fecha_entrada']

    def __str__(self):
        return f'{self.placa} — {self.get_trabajo_display()}'
    
class Solicitud(models.Model):

    SERVICIOS = [
        ('mecanica',  'Mecánica'),
        ('electrico', 'Eléctrico'),
        ('aire',      'Aire acondicionado'),
        ('latoneria', 'Latonería'),
        ('pintura',   'Pintura'),
    ]

    ESTADOS = [
        ('espera',       'En espera'),
        ('agendada',     'Agendada'),
        ('reprogramada', 'Reprogramada — pendiente cliente'),
        ('confirmada',   'Confirmada por cliente'),
        ('rechazada',    'Rechazada por cliente'),
        ('terminada',    'Servicio terminado'),
    ]

    # Datos del cliente
    usuario       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitudes')
    nombre        = models.CharField(max_length=100)
    telefono      = models.CharField(max_length=20)

    # Datos del vehículo
    placa         = models.CharField(max_length=6)  # ABC123
    modelo        = models.CharField(max_length=100)
    anio          = models.PositiveIntegerField(verbose_name='Año')

    # Servicio
    servicio      = models.CharField(max_length=20, choices=SERVICIOS)
    descripcion   = models.TextField(blank=True, verbose_name='Descripción del problema')

    # Fecha y hora que pide el cliente
    fecha_pedida  = models.DateField()
    hora_pedida   = models.TimeField()

    # Fecha y hora que propone el admin (solo si reprograma)
    fecha_admin   = models.DateField(null=True, blank=True)
    hora_admin    = models.TimeField(null=True, blank=True)

    # Estado
    estado        = models.CharField(max_length=20, choices=ESTADOS, default='espera')

    # Fechas de control
    creada_el     = models.DateTimeField(auto_now_add=True)
    actualizada   = models.DateTimeField(auto_now=True)

class MovimientoInventario(models.Model):
    TIPO = [
        ('entrada', 'Entrada'),
        ('salida',  'Salida'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, related_name='movimientos')
    tipo         = models.CharField(max_length=10, choices=TIPO)
    cantidad     = models.PositiveIntegerField()
    placa        = models.CharField(max_length=6, blank=True)
    servicio     = models.CharField(max_length=20, choices=Solicitud.SERVICIOS, blank=True)
    observacion  = models.TextField(blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha        = models.DateTimeField(auto_now_add=True)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.SET_NULL, null=True, blank=True, related_name='repuestos_usados')

    class Meta:
        verbose_name        = 'Movimiento de inventario'
        verbose_name_plural = 'Movimientos de inventario'
        ordering            = ['-fecha']

    def __str__(self):
        return f'{self.tipo} · {self.producto.nombre} · {self.cantidad} uds · {self.placa or "Sin placa"}'

producto = Producto
vehiculo = Vehiculo