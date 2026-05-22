from django.contrib import admin
from .models import producto, vehiculo

@admin.register(producto)
class productoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad', 'precio', 'creado_el')
    search_fields = ('nombre',)
    list_filter = ('cantidad',)

@admin.register(vehiculo)
class vehiculoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'trabajo', 'responsable', 'fecha_entrada', 'fecha_salida')
    search_fields = ('placa', 'responsable')
    list_filter = ('trabajo',)

