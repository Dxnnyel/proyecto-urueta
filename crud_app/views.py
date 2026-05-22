from datetime import date, timedelta
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ProductoForm, VehiculoForm
from .models import Producto, Vehiculo, CodigoVerificacion, Solicitud, MovimientoInventario

productoForm = ProductoForm
vehiculoForm = VehiculoForm

def es_admin(user):
    return user.is_staff


def inicio(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard' if request.user.is_staff else 'dashboard')
    return render(request, 'crud_app/inicio.html')


@login_required(login_url='login')
def home(request):
    return redirect('admin_dashboard' if request.user.is_staff else 'dashboard')


def login_user(request):
    if request.method == 'POST':
        identificador = request.POST.get('username', '').strip()
        password      = request.POST.get('password', '')
        user = authenticate(request, username=identificador, password=password)
        if user is None:
            try:
                u = User.objects.get(email__iexact=identificador)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass
        if user is not None:
            if not user.is_active:
                messages.error(request, 'Esta cuenta está desactivada.')
                return redirect('login')
            login(request, user)
            messages.success(request, f'Bienvenido, {user.first_name or user.username}')
            return redirect('admin_dashboard' if user.is_staff else 'dashboard')
        messages.error(request, 'Usuario/correo o contraseña incorrectos.')
        return redirect('login')
    return render(request, 'crud_app/login.html')


def logout_user(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('inicio')


def register_user(request):
    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip().lower()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return redirect('register')
        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return redirect('register')
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'Ese nombre de usuario ya está en uso.')
            return redirect('register')
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Ese correo ya tiene una cuenta registrada.')
            return redirect('register')

        CodigoVerificacion.objects.filter(email=email).delete()
        verificacion = CodigoVerificacion.objects.create(
            username=username,
            email=email,
            password=make_password(password1),
        )
        try:
            send_mail(
                subject='Tu código de verificación — Urueta & Urueta',
                message=(
                    f'Hola {username},\n\n'
                    f'Tu código de verificación es:\n\n'
                    f'        {verificacion.codigo}\n\n'
                    f'Este código es válido por 15 minutos.\n'
                    f'Si no creaste esta cuenta, ignora este correo.\n\n'
                    f'— Urueta & Urueta, Montería'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            verificacion.delete()
            messages.error(request, f'No pudimos enviar el correo: {e}')
            return redirect('register')

        request.session['verificar_email'] = email
        messages.success(request, f'Enviamos un código a {email}. Revisa también el spam.')
        return redirect('verificar_codigo')

    return render(request, 'crud_app/register.html')


def verificar_codigo(request):
    email = request.session.get('verificar_email')
    if not email:
        messages.error(request, 'Sesión expirada. Inicia el registro de nuevo.')
        return redirect('register')

    if request.method == 'POST':
        codigo_ingresado = request.POST.get('codigo', '').strip()
        try:
            verificacion = CodigoVerificacion.objects.get(email=email)
        except CodigoVerificacion.DoesNotExist:
            messages.error(request, 'No encontramos un código para este correo. Regístrate de nuevo.')
            return redirect('register')

        if verificacion.intentos >= 5:
            verificacion.delete()
            del request.session['verificar_email']
            messages.error(request, 'Demasiados intentos. Vuelve a registrarte.')
            return redirect('register')
        if verificacion.esta_expirado():
            verificacion.delete()
            del request.session['verificar_email']
            messages.error(request, 'El código expiró (15 min). Vuelve a registrarte.')
            return redirect('register')
        if codigo_ingresado != verificacion.codigo:
            verificacion.intentos += 1
            verificacion.save()
            restantes = 5 - verificacion.intentos
            messages.error(request, f'Código incorrecto. Te quedan {restantes} intento(s).')
            return redirect('verificar_codigo')

        user = User(
            username=verificacion.username,
            email=verificacion.email,
            is_active=True,
            is_staff=False,
        )
        user.password = verificacion.password
        user.save()
        verificacion.delete()
        del request.session['verificar_email']
        login(request, user)
        messages.success(request, f'¡Cuenta creada! Bienvenido, {user.username}.')
        return redirect('dashboard')

    return render(request, 'crud_app/verificar_codigo.html', {'email': email})


def reenviar_codigo(request):
    email = request.session.get('verificar_email')
    if not email:
        return redirect('register')
    try:
        verificacion = CodigoVerificacion.objects.get(email=email)
    except CodigoVerificacion.DoesNotExist:
        return redirect('register')

    import random, string
    verificacion.codigo    = ''.join(random.choices(string.digits, k=6))
    verificacion.intentos  = 0
    verificacion.creado_el = timezone.now()
    verificacion.save()

    try:
        send_mail(
            subject='Nuevo código — Urueta & Urueta',
            message=(
                f'Hola {verificacion.username},\n\n'
                f'Tu nuevo código es:\n\n'
                f'        {verificacion.codigo}\n\n'
                f'Válido por 15 minutos.\n\n'
                f'— Urueta & Urueta'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        messages.success(request, 'Enviamos un nuevo código a tu correo.')
    except Exception as e:
        messages.error(request, f'No pudimos reenviar: {e}')

    return redirect('verificar_codigo')


# ── DASHBOARDS ────────────────────────────────────────────────

@login_required(login_url='login')
def dashboard(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    return render(request, 'crud_app/usuario/dashboard.html')


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def admin_dashboard(request):
    total_productos        = Producto.objects.count()
    productos_bajo_stock   = Producto.objects.filter(cantidad__lt=5).count()
    total_solicitudes      = Solicitud.objects.count()
    solicitudes_pendientes = Solicitud.objects.filter(estado='espera').count()
    en_proceso             = Solicitud.objects.filter(estado__in=['agendada', 'confirmada', 'reprogramada']).count()
    terminadas             = Solicitud.objects.filter(estado='terminada').count()

    return render(request, 'crud_app/admin/dashboard.html', {
        'total_productos':        total_productos,
        'productos_bajo_stock':   productos_bajo_stock,
        'total_solicitudes':      total_solicitudes,
        'solicitudes_pendientes': solicitudes_pendientes,
        'en_proceso':             en_proceso,
        'terminadas':             terminadas,
    })


# ── INVENTARIO ────────────────────────────────────────────────

@login_required(login_url='login')
def inventario(request):
    query     = request.GET.get('q', '')
    productos = Producto.objects.all()
    if query:
        productos = productos.filter(nombre__icontains=query)
    return render(request, 'crud_app/inventario.html', {'productos': productos, 'query': query})


@login_required(login_url='login')
def lista_productos(request):
    productos = Producto.objects.all()
    return render(request, 'crud_app/lista_productos.html', {'productos': productos})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def crear_producto(request):
    if request.method == 'POST':
        nombre      = request.POST.get('nombre', '').strip()
        cantidad    = int(request.POST.get('cantidad', 0))
        precio      = request.POST.get('precio', 0)
        descripcion = request.POST.get('descripcion', '').strip()

        # Si ya existe el producto, suma cantidad
        existente = Producto.objects.filter(nombre__iexact=nombre).first()
        if existente:
            existente.cantidad += cantidad
            existente.save()
            MovimientoInventario.objects.create(
                producto=existente,
                tipo='entrada',
                cantidad=cantidad,
                observacion='Entrada adicional de stock',
                registrado_por=request.user,
            )
            messages.success(request, f'Se sumaron {cantidad} unidades a "{existente.nombre}". Stock actual: {existente.cantidad}.')
        else:
            producto_nuevo = Producto.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                cantidad=cantidad,
                precio=precio,
            )
            MovimientoInventario.objects.create(
                producto=producto_nuevo,
                tipo='entrada',
                cantidad=cantidad,
                observacion='Producto nuevo ingresado al inventario',
                registrado_por=request.user,
            )
            messages.success(request, f'Producto "{nombre}" creado con {cantidad} unidades.')

        return redirect('inventario')

    return render(request, 'crud_app/crear_producto.html', {
        'productos_existentes': Producto.objects.all()
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def actualizar_producto(request, pk):
    producto_obj = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, instance=producto_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto actualizado.')
        return redirect('lista_productos')
    return render(request, 'crud_app/actualizar_producto.html', {'form': form})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def eliminar_producto(request, pk):
    producto_obj = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto_obj.delete()
        messages.success(request, 'Producto eliminado.')
        return redirect('lista_productos')
    return render(request, 'crud_app/eliminar_producto.html', {'producto': producto_obj})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def registrar_salida(request):
    productos = Producto.objects.filter(cantidad__gt=0).order_by('nombre')

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad    = int(request.POST.get('cantidad', 1))
        placa       = request.POST.get('placa', '').strip().upper()
        servicio    = request.POST.get('servicio', '').strip()
        observacion = request.POST.get('observacion', '').strip()

        producto_obj = get_object_or_404(Producto, pk=producto_id)

        if cantidad > producto_obj.cantidad:
            messages.error(request, f'Stock insuficiente. Solo hay {producto_obj.cantidad} unidades de "{producto_obj.nombre}".')
            return redirect('registrar_salida')

        producto_obj.cantidad -= cantidad
        producto_obj.save()

        MovimientoInventario.objects.create(
            producto=producto_obj,
            tipo='salida',
            cantidad=cantidad,
            placa=placa,
            servicio=servicio,
            observacion=observacion,
            registrado_por=request.user,
        )
        messages.success(request, f'Salida registrada: {cantidad} x "{producto_obj.nombre}" para vehículo {placa or "N/A"}.')
        return redirect('inventario')

    return render(request, 'crud_app/registrar_salida.html', {'productos': productos})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def reporte_movimientos(request):
    fecha_str = request.GET.get('fecha', str(date.today()))
    tipo      = request.GET.get('tipo', '')

    movimientos = MovimientoInventario.objects.select_related('producto', 'registrado_por')
    if fecha_str:
        movimientos = movimientos.filter(fecha__date=fecha_str)
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)

    total_entradas = sum(m.cantidad for m in movimientos if m.tipo == 'entrada')
    total_salidas  = sum(m.cantidad for m in movimientos if m.tipo == 'salida')

    return render(request, 'crud_app/reporte_movimientos.html', {
        'movimientos':    movimientos,
        'fecha':          fecha_str,
        'tipo':           tipo,
        'total_entradas': total_entradas,
        'total_salidas':  total_salidas,
    })


@login_required(login_url='login')
def comprobante_repuestos(request, placa):
    movimientos = MovimientoInventario.objects.filter(
        placa__iexact=placa,
        tipo='salida'
    ).select_related('producto').order_by('-fecha')

    return render(request, 'crud_app/comprobante_repuestos.html', {
        'movimientos': movimientos,
        'placa': placa.upper(),
    })


# ── VEHÍCULOS ─────────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def crear_vehiculo(request):
    form = VehiculoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Vehículo registrado correctamente.')
        return redirect('admin_dashboard')
    return render(request, 'crud_app/crear_vehiculo.html', {'form': form})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def buscar_vehiculo(request):
    query      = request.GET.get('q', '').strip().upper()
    solicitudes = []
    repuestos   = []

    if query:
        solicitudes = Solicitud.objects.filter(
            placa__icontains=query
        ).order_by('-creada_el')

        repuestos = MovimientoInventario.objects.filter(
            placa__icontains=query,
            tipo='salida'
        ).select_related('producto', 'solicitud').order_by('-fecha')

    return render(request, 'crud_app/buscar.html', {
        'query':       query,
        'solicitudes': solicitudes,
        'repuestos':   repuestos,
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def historial_vehiculos(request):
    estado  = request.GET.get('estado', '')
    fecha   = request.GET.get('fecha', '')

    solicitudes = Solicitud.objects.select_related('usuario').order_by('-creada_el')

    if estado:
        solicitudes = solicitudes.filter(estado=estado)
    if fecha:
        solicitudes = solicitudes.filter(fecha_pedida=fecha)

    todas = Solicitud.objects.all()
    terminadas  = todas.filter(estado='terminada').count()
    en_proceso  = todas.filter(estado__in=['agendada', 'confirmada', 'reprogramada']).count()
    total       = todas.count()

    return render(request, 'crud_app/historial.html', {
        'solicitudes': solicitudes,
        'estado':      estado,
        'fecha':       fecha,
        'total':       total,
        'terminadas':  terminadas,
        'en_proceso':  en_proceso,
    })


# ── SOLICITUDES CLIENTE ───────────────────────────────────────

@login_required(login_url='login')
def nueva_solicitud(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        nombre       = request.POST.get('nombre', '').strip()
        telefono     = request.POST.get('telefono', '').strip()
        placa        = request.POST.get('placa', '').strip().upper()
        modelo       = request.POST.get('modelo', '').strip()
        anio         = request.POST.get('anio', '').strip()
        servicio     = request.POST.get('servicio', '').strip()
        descripcion  = request.POST.get('descripcion', '').strip()
        fecha_pedida = request.POST.get('fecha_pedida', '').strip()
        hora_pedida  = request.POST.get('hora_pedida', '').strip()

        if not re.match(r'^[A-Z]{3}[0-9]{3}$', placa):
            messages.error(request, 'La placa debe tener el formato colombiano: 3 letras y 3 números. Ejemplo: ABC123')
            return redirect('nueva_solicitud')
        
        # Evitar duplicados: misma placa, mismo servicio, mismo día
        duplicada = Solicitud.objects.filter(
            usuario=request.user,
            placa=placa,
            servicio=servicio,
            fecha_pedida=fecha_pedida,
            estado__in=['espera', 'agendada', 'confirmada', 'reprogramada']
        ).exists()

        if duplicada:
            messages.error(request, f'Ya tienes una solicitud activa para la placa {placa} con ese servicio en esa fecha.')
            return redirect('nueva_solicitud')

        Solicitud.objects.create(
            usuario=request.user, nombre=nombre, telefono=telefono,
            placa=placa, modelo=modelo, anio=anio, servicio=servicio,
            descripcion=descripcion, fecha_pedida=fecha_pedida, hora_pedida=hora_pedida,
        )
        messages.success(request, 'Solicitud enviada correctamente.')
        return redirect('mis_solicitudes')

    return render(request, 'crud_app/usuario/nueva_solicitud.html')


@login_required(login_url='login')
def mis_solicitudes(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    solicitudes = Solicitud.objects.filter(usuario=request.user)
    return render(request, 'crud_app/usuario/mis_solicitudes.html', {'solicitudes': solicitudes})


@login_required(login_url='login')
def responder_reprogramacion(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk, usuario=request.user)
    if solicitud.estado != 'reprogramada':
        messages.error(request, 'Esta solicitud no tiene una reprogramación pendiente.')
        return redirect('mis_solicitudes')
    if request.method == 'POST':
        respuesta = request.POST.get('respuesta')
        if respuesta == 'aceptar':
            solicitud.estado = 'confirmada'
            solicitud.save()
            messages.success(request, 'Confirmaste la nueva fecha. ¡Te esperamos!')
        elif respuesta == 'rechazar':
            solicitud.estado = 'rechazada'
            solicitud.save()
            messages.info(request, 'Rechazaste la reprogramación.')
    return redirect('mis_solicitudes')

# ── REPUESTOS POR SOLICITUD ───────────────────────────────────

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def agregar_repuesto_solicitud(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)

    if solicitud.estado not in ('agendada', 'confirmada', 'terminada'):
        messages.error(request, 'Solo puedes agregar repuestos a solicitudes agendadas o confirmadas.')
        return redirect('admin_gestionar_solicitud', pk=pk)

    productos = Producto.objects.filter(cantidad__gt=0).order_by('nombre')

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad    = int(request.POST.get('cantidad', 1))
        observacion = request.POST.get('observacion', '').strip()

        producto_obj = get_object_or_404(Producto, pk=producto_id)

        if cantidad > producto_obj.cantidad:
            messages.error(request, f'Stock insuficiente. Solo hay {producto_obj.cantidad} uds de "{producto_obj.nombre}".')
            return redirect('agregar_repuesto_solicitud', pk=pk)

        producto_obj.cantidad -= cantidad
        producto_obj.save()

        MovimientoInventario.objects.create(
            producto=producto_obj,
            tipo='salida',
            cantidad=cantidad,
            placa=solicitud.placa,
            servicio=solicitud.servicio,
            observacion=observacion,
            registrado_por=request.user,
            solicitud=solicitud,
        )
        messages.success(request, f'Repuesto "{producto_obj.nombre}" x{cantidad} agregado.')
        return redirect('agregar_repuesto_solicitud', pk=pk)

    repuestos_usados = MovimientoInventario.objects.filter(
        solicitud=solicitud, tipo='salida'
    ).select_related('producto').order_by('-fecha')

    return render(request, 'crud_app/admin/agregar_repuesto_solicitud.html', {
        'solicitud':        solicitud,
        'productos':        productos,
        'repuestos_usados': repuestos_usados,
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def eliminar_repuesto_solicitud(request, pk):
    movimiento = get_object_or_404(MovimientoInventario, pk=pk)
    solicitud_pk = movimiento.solicitud.pk

    # Devolver stock al producto
    if movimiento.producto:
        movimiento.producto.cantidad += movimiento.cantidad
        movimiento.producto.save()

    movimiento.delete()
    messages.success(request, 'Repuesto eliminado y stock restaurado.')
    return redirect('agregar_repuesto_solicitud', pk=solicitud_pk)

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def cerrar_servicio(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)

    if solicitud.estado not in ('agendada', 'confirmada'):
        messages.error(request, 'Solo puedes cerrar solicitudes agendadas o confirmadas.')
        return redirect('admin_gestionar_solicitud', pk=pk)

    if request.method == 'POST':
        solicitud.estado = 'terminada'
        solicitud.save()

        # Obtener repuestos usados en este servicio
        repuestos = MovimientoInventario.objects.filter(
            solicitud=solicitud, tipo='salida'
        ).select_related('producto')

        # Armar lista de repuestos para el email
        lista_repuestos = ''
        if repuestos:
            for r in repuestos:
                lista_repuestos += f'  - {r.producto.nombre}: {r.cantidad} uds\n'
        else:
            lista_repuestos = '  Sin repuestos registrados.\n'

        # Enviar email al cliente
        try:
            send_mail(
                subject='Tu vehículo está listo — Urueta & Urueta',
                message=(
                    f'Hola {solicitud.nombre},\n\n'
                    f'El servicio de {solicitud.get_servicio_display()} para tu vehículo '
                    f'con placa {solicitud.placa} ha sido completado.\n\n'
                    f'Repuestos utilizados:\n{lista_repuestos}\n'
                    f'Puedes ver el comprobante completo desde tu cuenta en nuestra plataforma.\n\n'
                    f'Gracias por confiar en nosotros.\n'
                    f'— Urueta & Urueta, Montería\n'
                    f'Calle 39 #1B-81 · 300 351 8699'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[solicitud.usuario.email],
                fail_silently=True,
            )
            messages.success(request, f'Servicio para {solicitud.placa} cerrado. Se notificó al cliente por email.')
        except Exception:
            messages.success(request, f'Servicio para {solicitud.placa} cerrado. No se pudo enviar el email.')

        return redirect('admin_solicitudes')

    return redirect('admin_gestionar_solicitud', pk=pk)

# ── SOLICITUDES ADMIN ─────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def admin_solicitudes(request):
    solicitudes = Solicitud.objects.all()
    return render(request, 'crud_app/admin/solicitudes.html', {'solicitudes': solicitudes})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard')
def admin_gestionar_solicitud(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'agendar':
            solicitud.estado = 'agendada'
            solicitud.save()
            try:
                send_mail(
                    subject='Tu cita fue confirmada — Urueta & Urueta',
                    message=(
                        f'Hola {solicitud.nombre},\n\n'
                        f'Tu solicitud de {solicitud.get_servicio_display()} para el vehículo '
                        f'con placa {solicitud.placa} ha sido CONFIRMADA.\n\n'
                        f'📅 Fecha: {solicitud.fecha_pedida}\n'
                        f'🕐 Hora: {solicitud.hora_pedida}\n\n'
                        f'Te esperamos en:\n'
                        f'Calle 39 #1B-81, Montería · 300 351 8699\n\n'
                        f'— Urueta & Urueta'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[solicitud.usuario.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f'Solicitud de {solicitud.placa} agendada. Cliente notificado.')

        elif accion == 'reprogramar':
            fecha_admin = request.POST.get('fecha_admin')
            hora_admin  = request.POST.get('hora_admin')
            if not fecha_admin or not hora_admin:
                messages.error(request, 'Debes ingresar la nueva fecha y hora.')
                return redirect('admin_gestionar_solicitud', pk=pk)
            solicitud.fecha_admin = fecha_admin
            solicitud.hora_admin  = hora_admin
            solicitud.estado      = 'reprogramada'
            solicitud.save()
            try:
                send_mail(
                    subject='Tu cita fue reprogramada — Urueta & Urueta',
                    message=(
                        f'Hola {solicitud.nombre},\n\n'
                        f'Tu solicitud de {solicitud.get_servicio_display()} para el vehículo '
                        f'con placa {solicitud.placa} ha sido REPROGRAMADA.\n\n'
                        f'El taller te propone una nueva fecha:\n'
                        f'📅 Fecha: {fecha_admin}\n'
                        f'🕐 Hora: {hora_admin}\n\n'
                        f'Ingresa a tu cuenta para aceptar o rechazar la nueva fecha.\n\n'
                        f'— Urueta & Urueta\n'
                        f'Calle 39 #1B-81, Montería · 300 351 8699'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[solicitud.usuario.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f'Reprogramación enviada. Cliente notificado.')

        return redirect('admin_solicitudes')
    return render(request, 'crud_app/admin/gestionar_solicitud.html', {'solicitud': solicitud})