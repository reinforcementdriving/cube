import os
import tensorflow as tf
from tools.utils import scales_to_255
import cv2
import numpy as np
import vispy
from network.config import cfg
from vispy.scene import visuals
import vispy.io as vispy_file
from os.path import join as path_add

vispy.set_log_level('CRITICAL', match='-.-')
folder = path_add(cfg.TEST_RESULT, cfg.RANDOM_STR)
os.makedirs(folder)
#  common functions  ===========================
def box3d_2conner(box):
    #box : score,x,y,z,l,w,h,type1,type2
    p0 = np.array([box[0] - float(box[3]) / 2.0, box[1] - float(box[4]) / 2.0, box[2] - float(box[5]) / 2.0, ])
    p1 = np.array([box[0] - float(box[3]) / 2.0, box[1] + float(box[4]) / 2.0, box[2] - float(box[5]) / 2.0, ])
    p2 = np.array([box[0] + float(box[3]) / 2.0, box[1] + float(box[4]) / 2.0, box[2] - float(box[5]) / 2.0, ])
    p3 = np.array([box[0] + float(box[3]) / 2.0, box[1] - float(box[4]) / 2.0, box[2] - float(box[5]) / 2.0, ])

    p4 = np.array([box[0] - float(box[3]) / 2.0, box[1] - float(box[4]) / 2.0, box[2] + float(box[5]) / 2.0, ])
    p5 = np.array([box[0] - float(box[3]) / 2.0, box[1] + float(box[4]) / 2.0, box[2] + float(box[5]) / 2.0, ])
    p6 = np.array([box[0] + float(box[3]) / 2.0, box[1] + float(box[4]) / 2.0, box[2] + float(box[5]) / 2.0, ])
    p7 = np.array([box[0] + float(box[3]) / 2.0, box[1] - float(box[4]) / 2.0, box[2] + float(box[5]) / 2.0, ])

    return p0,p1,p2,p3,p4,p5,p6,p7
#  using vispy ============================
class pcd_vispy_client(object):# TODO: qt-client TO BE RE-WRITE
    def __init__(self,QUEUE,title=None, keys='interactive', size=(800,600)):
        self.queue=QUEUE
        self.canvas = vispy.scene.SceneCanvas(title=title, keys=keys, size=size, show=True)
        grid = self.canvas.central_widget.add_grid()
        self.vb = grid.add_view(row=0, col=0, row_span=2)
        self.vb_img = grid.add_view(row=1, col=0)

        self.vb.camera = 'turntable'
        self.vb.camera.elevation = 21.0
        self.vb.camera.center = (6.5, -0.5, 9.0)
        self.vb.camera.azimuth = -75.5
        self.vb.camera.scale_factor = 32.7

        self.vb_img.camera = 'turntable'
        self.vb_img.camera.elevation = -90.0
        self.vb_img.camera.center = (2100, -380, -500)
        self.vb_img.camera.azimuth = 0.0
        self.vb_img.camera.scale_factor = 1500

        @self.canvas.connect
        def on_key_press(ev):
            if ev.key.name in '+=':
                a = self.vb.camera.get_state()
            print(a)

        self.input_data()

        vispy.app.run()

    def input_data(self,scans,img,boxes,index,save_img,no_gt):
        pos = scans[:, :3]
        scatter = visuals.Markers()
        scatter.set_gl_state('translucent', depth_test=False)
        scatter.set_data(pos, edge_width=0, face_color=(1, 1, 1, 1), size=0.01, scaling=True)
        self.vb.add(scatter)

        if img is None:
            img=np.zeros(shape=[1,1,3],dtype=np.float32)
        image = visuals.Image(data=img, method='auto')
        self.vb_img.add(image)

        if boxes is not None:
            boxes = boxes.reshape(-1, 9)
            gt_indice = np.where(boxes[:, -1] == 2)[0]
            gt_cnt = len(gt_indice)
            i = 0
            for box in boxes:
                radio = max(box[0] - 0.5, 0.005)*2.0
                color = (0, radio, 0, 1)  # Green

                if box[-1] == 4:  #  gt boxes
                    i = i + 1
                    vsp_box = visuals.Box(width=box[4],  depth=box[5],height=box[6], color=(0.6, 0.8, 0.0, 0.3))#edge_color='yellow')
                    mesh_box = vsp_box.mesh.mesh_data
                    mesh_border_box = vsp_box.border.mesh_data
                    vertices = mesh_box.get_vertices()
                    center = np.array([box[1], box[2], box[3]], dtype=np.float32)
                    vtcs = np.add(vertices, center)
                    mesh_border_box.set_vertices(vtcs)
                    mesh_box.set_vertices(vtcs)
                    self.vb.add(vsp_box)
                    if False:
                        text = visuals.Text(text='gt: ({}/{})'.format(i, gt_cnt), color='white', face='OpenSans', font_size=12,
                                            pos=[box[1], box[2], box[3]],anchor_x='left', anchor_y='top', font_manager=None)
                        self.vb.add(text)

                if (box[-1]+box[-2]) == 0: # True negative cls rpn divided by cube
                    self.vb.add(line_box(box,color=color))
                if (box[-1]+box[-2]) == 1: # False negative cls rpn divided by cube
                    self.vb.add(line_box(box,color='red'))
                if (box[-1]+box[-2]) == 2: # False positive cls rpn divided by cube
                    if no_gt:
                        self.vb.add(line_box(box, color='yellow'))
                    else:
                        self.vb.add(line_box(box, color='blue'))
                if (box[-1]+box[-2]) == 3: # True positive cls rpn divided by cube
                    self.vb.add(line_box(box,color='yellow'))

        if save_img:
            fileName = path_add(folder,str(index).zfill(6)+'.png')
            res = self.canvas.render(bgcolor='black')[:,:,0:3]
            vispy_file.write_png(fileName, res)

    def get_thread_data(self,QUEUE):
        if not QUEUE.empty():
            msg = QUEUE.get() # from class msg_qt(object) in file: cubic_train
            scans =msg.scans
            img=msg.img
            boxes=msg.boxes
            index=msg.index
            save_img=msg.save_img
            no_gt=msg.no_gt

def pcd_vispy(scans=None,img=None, boxes=None, name=None, index=0,vis_size=(800, 600),save_img=False,visible=True,no_gt=False,multi_vis=False):
    if multi_vis:
        canvas = vispy.scene.SceneCanvas(title=name, keys='interactive', size=vis_size,show=True)
    else:
        canvas = vispy.scene.SceneCanvas(title=name, keys='interactive', size=vis_size,show=visible)
    grid = canvas.central_widget.add_grid()
    vb = grid.add_view(row=0, col=0, row_span=2)
    vb_img = grid.add_view(row=1, col=0)

    pos = scans[:, :3]
    scatter = visuals.Markers()
    scatter.set_gl_state('translucent', depth_test=False)
    scatter.set_data(pos, edge_width=0, face_color=(1, 1, 1, 1), size=0.02, scaling=True)

    vb.camera = 'turntable'
    vb.camera.elevation = 21.0
    vb.camera.center = (6.5, -0.5, 9.0)
    vb.camera.azimuth = -75.5
    vb.camera.scale_factor = 32.7
    vb.add(scatter)

    if img is None:
        img=np.zeros(shape=[1,1,3],dtype=np.float32)
    image = visuals.Image(data=img, method='auto')
    vb_img.camera = 'turntable'
    vb_img.camera.elevation = -90.0
    vb_img.camera.center = (2100, -380, -500)
    vb_img.camera.azimuth = 0.0
    vb_img.camera.scale_factor = 1500
    vb_img.add(image)

    if boxes is not None:
        if len(boxes.shape) ==1:
            boxes = boxes.reshape(1,-1)
        gt_indice = np.where(boxes[:, -1] == 4)[0]
        gt_cnt = len(gt_indice)
        i = 0
        for box in boxes:
            radio = max(box[6] - 0.5, 0.005)*2.0
            color = (0, radio, 0, 1)  # Green

            if box[-1] == 4:  #  gt boxes
                i = i + 1
                vsp_box = visuals.Box(width=box[3],  depth=box[4],height=box[5], color=(0.3, 0.4, 0.0, 0.06),edge_color='pink')
                mesh_box = vsp_box.mesh.mesh_data
                mesh_border_box = vsp_box.border.mesh_data
                vertices = mesh_box.get_vertices()
                center = np.array([box[0], box[1], box[2]], dtype=np.float32)
                vtcs = np.add(vertices, center)
                mesh_border_box.set_vertices(vtcs)
                mesh_box.set_vertices(vtcs)
                vb.add(vsp_box)
                if False:
                    text = visuals.Text(text='gt: ({}/{})'.format(i, gt_cnt), color='white', face='OpenSans', font_size=12,
                                        pos=[box[0], box[1], box[2]],anchor_x='left', anchor_y='top', font_manager=None)
                    vb.add(text)
            elif len(box)!=9:
                if box[-1] == 1:
                    vb.add(line_box(box, color='yellow'))
                else:
                    vb.add(line_box(box, color='pink'))
            elif (box[-1]+box[-2]) == 0: # True negative cls rpn divided by cube
                vb.add(line_box(box,color=color))
            elif (box[-1]+box[-2]) == 1: # False negative cls rpn divided by cube
                vb.add(line_box(box,color='red'))
            elif (box[-1]+box[-2]) == 2: # False positive cls rpn divided by cube
                if no_gt:
                    pass
                    vb.add(line_box(box, color='yellow'))
                else:
                    pass
                    vb.add(line_box(box, color='blue'))
            elif (box[-1]+box[-2]) == 3: # True positive cls rpn divided by cube
                vb.add(line_box(box,color='yellow'))
            text = visuals.Text(text='vertex:0', color='white', face='OpenSans', font_size=12,
                                pos=[box[0]-box[3]/2, box[1]-box[4]/2, box[2]-box[5]/2], anchor_x='left', anchor_y='top', font_manager=None)
            vb.add(text)

    if save_img:
        fileName = path_add(folder,str(index).zfill(6)+'.png')
        res = canvas.render(bgcolor='black')[:,:,0:3]
        vispy_file.write_png(fileName, res)

    @canvas.connect
    def on_key_press(ev):
        if ev.key.name in '+=':
            a = vb.camera.get_state()
        print(a)

    if visible:
        pass
        vispy.app.run()

    return canvas

def pcd_show_now():
    vispy.app.run()
    vispy.app.quit()

def vispy_init():
    import vispy
    vispy.use('pyqt4')
    # vispy.app.use_app()
    v = vispy.app.Canvas()

def line_box(box,color=(0, 1, 0, 0.1)):
    p0, p1, p2, p3, p4, p5, p6, p7=box3d_2conner(box)
    pos = np.vstack((p0,p1,p2,p3,p0,p4,p5,p6,p7,p4,p5,p1,p2,p6,p7,p3))
    lines = visuals.Line(pos=pos, connect='strip', width=1, color=color, antialias=True,method='gl')

    return lines

#  using RViz  ===========================

def Boxes_labels_Gen(box_es,ns,frame_id='rslidar'):
    from visualization_msgs.msg import Marker,MarkerArray
    from geometry_msgs.msg import Point,Vector3,Quaternion
    from std_msgs.msg import ColorRGBA

    def one_box(box_,color,index):
        marker = Marker()
        marker.id = index
        marker.ns= ns
        marker.header.frame_id = frame_id
        marker.type = marker.LINE_STRIP
        marker.action = marker.ADD
        # marker.frame_locked=False
        # marker scale
        marker.scale = Vector3(0.04, 0.04, 0.04)  # x,yz
        # marker color
        marker.color = ColorRGBA(color[0], color[1], color[2], color[3])  # r,g,b,a
        # marker orientaiton
        marker.pose.orientation = Quaternion(0., 0., 0., 1.)  # x,y,z,w
        # marker position
        marker.pose.position = Point(0., 0., 0.)  # x,y,z
        # marker.lifetime = rospy.Duration(0.1)
        p0, p1, p2, p3, p4, p5, p6, p7 = box3d_2conner(box_)
        # marker line points
        marker.points = []
        for p in [p0, p1, p2, p3, p0, p4, p5, p6, p7, p4, p5, p1, p2, p6, p7, p3]:
            marker.points.append(Point(p[0], p[1], p[2], ))

        return marker

    def delete_all_markers(box_,color,index):
        marker = Marker()
        marker.id = index
        marker.ns = ns
        marker.header.frame_id = frame_id
        marker.type = marker.LINE_STRIP
        marker.action = 3 # marker.DELETEALL: deletes all objects
        # marker.frame_locked=False
        # marker scale
        marker.scale = Vector3(0.04, 0.04, 0.04)  # x,yz
        # marker color
        marker.color = ColorRGBA(color[0], color[1], color[2], color[3])  # r,g,b,a
        # marker orientaiton
        marker.pose.orientation = Quaternion(0., 0., 0., 1.)  # x,y,z,w
        # marker position
        marker.pose.position = Point(0., 0., 0.)  # x,y,z
        # marker.lifetime = rospy.Duration(0.1)
        p0, p1, p2, p3, p4, p5, p6, p7 = box3d_2conner(box_)
        # marker line points
        marker.points = []
        for p in [p0, p1, p2, p3, p0, p4, p5, p6, p7, p4, p5, p1, p2, p6, p7, p3]:
            marker.points.append(Point(p[0], p[1], p[2], ))

        return marker

    label_boxes = MarkerArray()
    label_boxes.markers=[]
    for idx,_box in enumerate(box_es):
        if _box[-1]==4:
            color_ = (1., 1., 0., 1)  # yellow
        else:
            color_ = (0., 1., 0., 1)  # green
        if idx == 0:
            label_boxes.markers.append(delete_all_markers(_box, color_, idx))
        label_boxes.markers.append(one_box(_box,color_,idx))

    return label_boxes

def PointCloud_Gen(points,frameID='rslidar'):
    from sensor_msgs.msg import PointCloud, ChannelFloat32
    from geometry_msgs.msg import Point32

    ##=========PointCloud===============
    points.dtype = np.float32
    point_cloud = points.reshape((-1, 4))
    pointx = point_cloud[:, 0].flatten()
    pointy = point_cloud[:, 1].flatten()
    pointz = point_cloud[:, 2].flatten()
    intensity = point_cloud[:, 3].flatten()
    # labels = point_cloud[:,6].flatten()

    seg_point = PointCloud()
    seg_point.header.frame_id = frameID
    channels1 = ChannelFloat32()
    seg_point.channels.append(channels1)
    seg_point.channels[0].name = "rgb"
    channels2 = ChannelFloat32()
    seg_point.channels.append(channels2)
    seg_point.channels[1].name = "intensity"

    for i in range(point_cloud.shape[0]):
        seg_point.channels[1].values.append(intensity[i])
        if True:  # labels[i] == 1:
            seg_point.channels[0].values.append(255)
            geo_point = Point32(pointx[i], pointy[i], pointz[i])
            seg_point.points.append(geo_point)
        else:
            seg_point.channels[0].values.append(255255255)
            geo_point = Point32(pointx[i], pointy[i], pointz[i])
            seg_point.points.append(geo_point)
            # elif result[i] == 2:
            #     seg_point.channels[0].values.append(255255255)
            #     geo_point = Point32(pointx[i], pointy[i], pointz[i])
            #     seg_point.points.append(geo_point)
            # elif result[i] == 3:
            #     seg_point.channels[0].values.append(255000)
            #     geo_point = Point32(pointx[i], pointy[i], pointz[i])
            #     seg_point.points.append(geo_point)

    return seg_point

#  using mayavi ===========================

def lidar_3d_to_corners(pts_3D):
    """
    convert pts_3D_lidar (x, y, z, l, w, h) to
    8 corners (x0, ... x7, y0, ...y7, z0, ... z7)
    """

    l = pts_3D[:, 3]
    w = pts_3D[:, 4]
    h = pts_3D[:, 5]

    l = l.reshape(-1, 1)
    w = w.reshape(-1, 1)
    h = h.reshape(-1, 1)

    # clockwise, zero at bottom left
    x_corners = np.hstack((l / 2., l / 2., -l / 2., -l / 2., l / 2., l / 2., -l / 2., -l / 2.))
    y_corners = np.hstack((w / 2., -w / 2., -w / 2., w / 2., w / 2., -w / 2., -w / 2., w / 2.))
    z_corners = np.hstack((-h / 2., -h / 2., -h / 2., -h / 2., h / 2., h / 2., h / 2., h / 2.))

    corners = np.hstack((x_corners, y_corners, z_corners))

    corners[:, 0:8] = corners[:, 0:8] + pts_3D[:, 0].reshape((-1, 1)).repeat(8, axis=1)
    corners[:, 8:16] = corners[:, 8:16] + pts_3D[:, 1].reshape((-1, 1)).repeat(8, axis=1)
    corners[:, 16:24] = corners[:, 16:24] + pts_3D[:, 2].reshape((-1, 1)).repeat(8, axis=1)

    return corners

def draw_3dPoints_box(lidar=None, Boxes3D=None, is_grid=True, fig=None, draw_axis=True):
    import mayavi.mlab as mlab  # 3d point

    pxs = lidar[:, 0]
    pys = lidar[:, 1]
    pzs = lidar[:, 2]
    prs = lidar[:, 3]

    if fig is None:
        fig = mlab.figure(figure=None, bgcolor=(0, 0, 0), fgcolor=None, engine=None, size=(1000, 500))
        pass

    if lidar is not None:
        mlab.points3d(pxs, pys, pzs, prs,
                      mode='point',  # 'point'  'sphere'
                      colormap='gnuplot',  # 'bone',  #'spectral',  #'copper',
                      scale_factor=1,
                      figure=fig)

    if Boxes3D is not None:
        for i in range(Boxes3D.shape[0]):
            b = lidar_3d_to_corners(Boxes3D[i, 1:7].reshape(-1, 6)).reshape(3, 8).transpose()
            a = round(Boxes3D[i, 0], 2)
            if a == 1.0:
                mycolor = (0., 1., 0.)
            else:
                a = max(a - 0.6, 0.025) * 2.5 + 0.01
                mycolor = (a, a, a)

            for k in range(0, 4):
                # http://docs.enthought.com/mayavi/mayavi/auto/mlab_helper_functions.html
                i, j = k, (k + 1) % 4
                mlab.plot3d([b[i, 0], b[j, 0]], [b[i, 1], b[j, 1]], [b[i, 2], b[j, 2]], color=mycolor, tube_radius=None,
                            line_width=1, figure=fig)

                i, j = k + 4, (k + 1) % 4 + 4
                mlab.plot3d([b[i, 0], b[j, 0]], [b[i, 1], b[j, 1]], [b[i, 2], b[j, 2]], color=mycolor, tube_radius=None,
                            line_width=1, figure=fig)

                i, j = k, k + 4
                mlab.plot3d([b[i, 0], b[j, 0]], [b[i, 1], b[j, 1]], [b[i, 2], b[j, 2]], color=mycolor, tube_radius=None,
                            line_width=1, figure=fig)

    # draw grid
    if is_grid:
        mlab.points3d(0, 0, 0, color=(1, 1, 1), mode='sphere', scale_factor=0.2)
        for y in np.arange(-40, 40, 5):
            x1, y1, z1 = -40.0, float(y), -1.5
            x2, y2, z2 = 40.0, float(y), -1.5
            mlab.plot3d([x1, x2], [y1, y2], [z1, z2], color=(0.1, 0.1, 0.1), tube_radius=None, line_width=0.1,
                        figure=fig)

        for x in np.arange(-40, 40, 5):
            x1, y1, z1 = float(x), -40.0, -1.5
            x2, y2, z2 = float(x), 40.0, -1.5
            mlab.plot3d([x1, x2], [y1, y2], [z1, z2], color=(0.1, 0.1, 0.1), tube_radius=None, line_width=0.1,
                        figure=fig)

    # draw axis
    if draw_axis:
        mlab.points3d(0, 0, 0, color=(1, 1, 1), mode='sphere', scale_factor=0.2)
        axes = np.array([
            [2., 0., 0., 0.],
            [0., 2., 0., 0.],
            [0., 0., 2., 0.],
        ], dtype=np.float64)
        fov = np.array([
            [40., 40., 0., 0.],
            [40., -40., 0., 0.],
        ], dtype=np.float64)

        mlab.plot3d([0, axes[0, 0]], [0, axes[0, 1]], [0, axes[0, 2]], color=(1, 0, 0), tube_radius=None, figure=fig)
        mlab.plot3d([0, axes[1, 0]], [0, axes[1, 1]], [0, axes[1, 2]], color=(0, 1, 0), tube_radius=None, figure=fig)
        mlab.plot3d([0, axes[2, 0]], [0, axes[2, 1]], [0, axes[2, 2]], color=(0, 0, 1), tube_radius=None, figure=fig)
        mlab.plot3d([0, fov[0, 0]], [0, fov[0, 1]], [0, fov[0, 2]], color=(1, 1, 1), tube_radius=None, line_width=1,
                    figure=fig)
        mlab.plot3d([0, fov[1, 0]], [0, fov[1, 1]], [0, fov[1, 2]], color=(1, 1, 1), tube_radius=None, line_width=1,
                    figure=fig)

    mlab.orientation_axes()
    mlab.view(azimuth=180, elevation=None, distance=50, focalpoint=[12.0909996, -1.04700089, -2.03249991])

    mlab.show()

def show_rpn_tf(img, cls_bv):#TODO
    bv_data = tf.reshape(img[:, :, :, 8], (601, 601, 1))
    bv_data = scales_to_255(bv_data, 0, 3, tf.float32)
    bv_img = tf.reshape(tf.stack([bv_data, bv_data, bv_data], 3), (601, 601, 3))

    return tf.py_func(show_bbox, [bv_img, cls_bv], tf.float32)

def show_bbox(bv_image, cls_bv):
    cnt = cls_bv.shape[0]
    for i in range(cnt):
        if cls_bv[i, 0] == 0:
            cv2.rectangle(bv_image, (cls_bv[i, 0], cls_bv[i, 1]), (cls_bv[i, 2], cls_bv[i, 3]), color=(0, 30, 0))
        else:
            cv2.rectangle(bv_image, (cls_bv[i, 0], cls_bv[i, 1]), (cls_bv[i, 2], cls_bv[i, 3]), color=(60, 60, 0))
    # filePath = "/media/disk4/deeplearningoflidar/he/CombiNet-he/output/"
    # cv2.imwrite(filePath+fileName,bv_image)
    return bv_image

#  normal functions ======================

def test_show_rpn_tf(img, box_pred=None):
    bv_data = tf.reshape(img[:, :, :, 8],(601, 601, 1))
    bv_data = scales_to_255(bv_data,0,3,tf.float32)
    bv_img = tf.reshape(tf.stack([bv_data,bv_data,bv_data],3),(601,601,3))
    return tf.py_func(test_show_bbox, [bv_img,box_pred], tf.float32)

def test_show_bbox(bv_image, bv_box):
    for i in range(bv_box.shape[0]):
        a = bv_box[i, 0]*255
        color_pre = (a, a, a)
        cv2.rectangle(bv_image, (bv_box[i, 1], bv_box[i, 2]), (bv_box[i, 3], bv_box[i, 4]), color=color_pre)

    return bv_image


if __name__ == '__main__':
    import rospy
    from visualization_msgs.msg import Marker, MarkerArray

    boxes =np.array([[1,1,1,1,1,1,1,1,1],[1,3,3,1,1,1,1,1,1]])
    rospy.init_node('node_labels')
    label_pub = rospy.Publisher('labels', MarkerArray, queue_size=100)
    rospy.loginfo('Ros begin ...')
    label_box = Boxes_labels_Gen(boxes,ns='test_box')
    while True:
        label_pub.publish(label_box)
