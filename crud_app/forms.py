from django import forms
from .models import Producto, Vehiculo


class ProductoForm(forms.ModelForm):
    class Meta:
        model  = Producto
        fields = ['nombre', 'descripcion', 'cantidad', 'precio']
        widgets = {
            'nombre':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción'}),
            'cantidad':    forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad'}),
            'precio':      forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Precio unitario'}),
        }


class VehiculoForm(forms.ModelForm):
    class Meta:
        model  = Vehiculo
        fields = ['placa', 'observaciones', 'trabajo', 'responsable', 'fecha_salida']
        widgets = {
            'placa':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Placa del vehículo'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'trabajo':       forms.Select(attrs={'class': 'form-select'}),
            'responsable':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Responsable'}),
            'fecha_salida':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


productoForm = ProductoForm
vehiculoForm = VehiculoForm