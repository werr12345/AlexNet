import os
import numpy as np
import tensorflow as tf
import data_loader
import model
import time
import matplotlib.pyplot as plt

class AlexNet:
    def __init__(self, input_size, lr=0.01, momentum=0.9, decaying_factor=0.0005,
                 LRN_depth=5, LRN_bias=2, LRN_alpha=0.0001, LRN_beta=0.75, keep_prob=0.8):
        self.input_size = input_size
        self.lr = lr
        self.momentum = momentum
        self.decaying_factor = decaying_factor

        self.LRN_depth = LRN_depth
        self.LRN_bias = LRN_bias
        self.LRN_alpha = LRN_alpha
        self.LRN_beta = LRN_beta
        self.keep_prob = keep_prob

        self.loss_sampling_step = None
        self.acc_sampling_step = None

        ###for plotting
        self.metric_list = dict()
        self.metric_list['losses'] = []
        self.metric_list['train_acc'] = []
        self.metric_list['val_acc'] = []

        self.graph = None
        self.model = model.AlexNetModel(input_size, decaying_factor=self.decaying_factor, LRN_depth=self.LRN_depth,
                                        LRN_bias=self.LRN_bias, LRN_alpha=self.LRN_alpha, LRN_beta=LRN_beta)

    def make_graph(self, input_, label_, keep_prob_, learning_rate_):
        logit = self.model.classifier(input_, keep_prob=keep_prob_)
        prediction = tf.argmax(logit, axis=1)

        CEE = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=label_, logits=logit))
        tf.add_to_collection('losses', CEE)

        ##### must minimize total loss
        total_loss = tf.add_n(tf.get_collection('losses'))
        train_op = tf.train.MomentumOptimizer(learning_rate=learning_rate_, momentum=self.momentum).minimize(total_loss)

        ##### but we need to watch Cross Entropy Error
        ##### to watch how well our model does converge.
        return train_op, prediction, CEE

    def run(self, max_epoch, loss_sampling_step, acc_sampling_step):
        self.loss_sampling_step = loss_sampling_step
        self.acc_sampling_step = acc_sampling_step

        self.graph = tf.Graph()

        with self.graph.as_default():
            loader = data_loader.DataLoader()

            X = tf.placeholder(shape=[None, 227, 227, 3], dtype=tf.float32)
            Y = tf.placeholder(shape=[None, 2], dtype=tf.float32)
            keep_prob = tf.placeholder(dtype=tf.float32)
            learning_rate = tf.placeholder(dtype=tf.float32)
            train_op, prediction_, loss_ = self.make_graph(X, Y, keep_prob, learning_rate)
            correct_prediction = tf.equal(prediction_, tf.argmax(Y, axis=1))
            accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

            config = tf.ConfigProto()
            config.gpu_options.allow_growth = True
            sess = tf.Session(config=config)

            saver = tf.train.Saver(tf.global_variables())
            ckpt = tf.train.get_checkpoint_state('./model')
            if ckpt and tf.train.checkpoint_exists(ckpt.model_checkpoint_path):
                saver.restore(sess, ckpt.model_checkpoint_path)
            else:
                sess.run(tf.global_variables_initializer())

            start_time = time.time()
            for epoch in range(max_epoch):
                train_accuracy = 0
                for itr in range(len(loader.idx_train)//self.input_size):
                    input_batch, label_batch = loader.next_train(self.input_size)
                    _, loss, tmpacc = sess.run([train_op, loss_, accuracy],
                                               feed_dict={X: input_batch, Y: label_batch,
                                                          keep_prob: self.keep_prob, learning_rate: self.lr})
                    train_accuracy = train_accuracy + tmpacc / (len(loader.idx_train) // self.input_size) * 100

                    #######################################################################
                    ############################## for debug ##############################
                    # if itr % 1 == 0:
                    #     W1_1, W1_2, \
                    #     W2_1, W2_2, \
                    #     W3, W4_1, \
                    #     W4_2, W5_1, \
                    #     W5_2, W6, \
                    #     W7, W8, \
                    #     L1_1, L1_2, \
                    #     L2_1, L2_2, \
                    #     L3, L4_1, \
                    #     L4_2, L5, \
                    #     L6, L7, \
                    #     L8, Logit \
                    #         = sess.run([self.model.W1_1, self.model.W1_2,
                    #                     self.model.W2_1, self.model.W2_2,
                    #                     self.model.W3, self.model.W4_1,
                    #                     self.model.W4_2, self.model.W5_1,
                    #                     self.model.W5_2, self.model.W6,
                    #                     self.model.W7, self.model.W8,
                    #                                        self.model.L1_1, self.model.L1_2,
                    #                                        self.model.L2_1, self.model.L2_2,
                    #                                        self.model.L3, self.model.L4_1,
                    #                                        self.model.L4_2, self.model.L5,
                    #                                        self.model.L6, self.model.L7,
                    #                                        self.model.L8, self.model.logit],
                    #                           feed_dict={X: input_batch, Y: label_batch,
                    #                                      keep_prob: 1.0, learning_rate: self.lr})
                    #
                    #     opt = tf.train.MomentumOptimizer(0.01, self.momentum)
                    #     grad = opt.compute_gradients(loss_, tf.trainable_variables())
                    #     G = sess.run(grad, feed_dict={X: input_batch, Y: label_batch,
                    #                                         keep_prob: 1.0, learning_rate: self.lr})
                    #
                    #     print()
                    #############################################################################
                    #############################################################################

                    if itr % loss_sampling_step == 0:
                        progress_view = 'progress : ' + '%7.6f' % (
                                    itr / (len(loader.idx_train)//self.input_size) * 100) + '%  loss :' + '%7.6f' % loss
                        print(progress_view)
                        self.metric_list['losses'].append(loss)

                with open('loss.txt', 'a') as wf:
                    epoch_time = time.time() - start_time
                    loss_info = '\nepoch: ' + '%7d' % (
                            epoch + 1) + '  batch loss: ' + '%7.6f' % loss + '  time elapsed: ' + '%7.6f' % epoch_time
                    wf.write(loss_info)

                W1_1, W1_2 = sess.run([self.model.W1_1, self.model.W1_2],
                                      feed_dict={X: input_batch, Y: label_batch,
                                                 keep_prob: 1.0, learning_rate: self.lr})
                self.save_W1(W1_1, W1_2, epoch)

                if epoch % acc_sampling_step == 0:
                    val_accuracy = 0

                    for i in range(len(loader.idx_val)//self.input_size):
                        input_batch, label_batch = loader.next_val(self.input_size)
                        tmpacc = sess.run(accuracy,
                                          feed_dict={X: input_batch, Y: label_batch,
                                                     keep_prob: 1.0, learning_rate: self.lr})
                        val_accuracy = val_accuracy + tmpacc / (len(loader.idx_val)//self.input_size) * 100

                    self.reg_acc(val_accuracy, train_accuracy)

                    if epoch % 10 == 0 and epoch != 0:
                        model_dir = './model' + '_epoch' + str(
                            epoch + 1) + '/model.ckpt'
                        saver.save(sess, model_dir)

                        ##### update learning rate
                        self.check_acc_adjust_lr(2)

                model_dir = './model' + '/model.ckpt'
                saver.save(sess, model_dir)
            sess.close()

    def check_acc_adjust_lr(self, threshold):
        list_acc = self.metric_list['train_acc'][-10:-1]
        last_acc = self.metric_list['train_acc'][-1]

        mean_acc_increased = 0
        for acc in list_acc:
            mean_acc_increased += (last_acc - acc)/len(list_acc)

        if mean_acc_increased < threshold:
            self.lr = self.lr / 10
            print('[learning rate reducing]')
            with open('loss.txt', 'a') as wf:
                wf.write('[learning rate reducing]')



    def save_acc(self):
        x = range(1, self.acc_sampling_step * len(self.metric_list['val_acc']) + 1, self.acc_sampling_step)

        y1 = self.metric_list['val_acc']
        y2 = self.metric_list['train_acc']

        plt.plot(x, y1, label='val_acc')
        plt.plot(x, y2, label='train_acc')

        plt.xlabel('Epoch')
        plt.ylabel('Acc')

        plt.legend(loc=4)
        plt.grid(True)
        plt.tight_layout()

        file_name = 'acc' + '.png'
        plt.savefig(file_name)

        plt.close()

    def save_loss(self):
        x = range(1, self.loss_sampling_step * len(self.metric_list['losses']) + 1, self.loss_sampling_step)

        y1 = self.metric_list['losses']

        plt.plot(x, y1, label='loss')

        plt.xlabel('Iter')
        plt.ylabel('Loss')

        plt.legend(loc=4)
        plt.grid(True)
        plt.tight_layout()

        file_name = 'loss' + '.png'
        plt.savefig(file_name)
        plt.close()

    def save_W1(self, W1_1, W1_2, epoch, dir_path='./first_kernel_visualization'):
        W1 = np.concatenate((W1_1, W1_2), axis=3)
        W1 = np.transpose(W1, (3, 0, 1, 2))

        #normalize W1
        max_W1 = np.max(W1)
        min_W1 = np.min(W1)
        W1 = (W1 - min_W1) / (max_W1-min_W1)

        if not (os.path.exists(dir_path)):
            os.mkdir(dir_path)
        grid_h = 6
        grid_w = 16

        fig, ax = plt.subplots(grid_h, grid_w, figsize=(16, 8))
        for i in range(grid_h):
            for j in range(grid_w):
                ax[i, j].get_xaxis().set_visible(False)
                ax[i, j].get_yaxis().set_visible(False)

        for k in range(0, grid_h * grid_w):
            i = k // grid_w
            j = k % grid_w
            ax[i, j].cla()
            ax[i, j].imshow(W1[k])

        label = 'Epoch {0}'.format(epoch)
        fig.text(0.5, 0.04, label, ha='center')
        plt.savefig(os.path.join(dir_path, 'result%04d.png' % epoch))
        plt.close()
        np.save(os.path.join(dir_path, 'result%04d.npy' % epoch), W1)

    def reg_acc(self, val_accuracy, train_accuracy) :
        print('test accuracy %g' % val_accuracy)
        print('train accuracy %g' % train_accuracy)
        self.metric_list['val_acc'].append(val_accuracy)
        self.metric_list['train_acc'].append(train_accuracy)
        with open('loss.txt', 'a') as wf:
            acc = '\ntest accuracy: ' + '%7g' % val_accuracy
            wf.write(acc)
            acc = '\ntrain accuracy: ' + '%7g' % train_accuracy
            wf.write(acc)