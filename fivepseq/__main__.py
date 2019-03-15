"""
The fivepseq entry point.
"""
# PORT
# argparse was written for argparse in Python 3.
# A few details are different in 2.x, especially some exception messages, which were improved in 3.x.
import argparse
import glob

import os
import logging
import shutil
import sys
import time

import dill

from fivepseq import config
from fivepseq.logic.structures.fivepseq_counts import FivePSeqCounts
from fivepseq.util.readers import BamReader, AnnotationReader, FastaReader
from fivepseq.util.formatting import pad_spaces
from fivepseq.logic.structures.fivepseq_counts import CountManager
from fivepseq.util.writers import FivePSeqOut
from fivepseq.logic.algorithms.general_pipelines.count_pipeline import CountPipeline
from logic.algorithms.general_pipelines.viz_pipeline import VizPipeline


class FivepseqArguments:
    """
    This class is for reading, parsing, storing and printing command line arguments.
    """
    logger = None

    def __init__(self):
        """
        Initializes FivepseqArguments with command line arguments.
        Stores those in the <args> attribute.
        """

        ###############################
        #       fivepseq common args
        ###############################

        parser = argparse.ArgumentParser(prog="fivepseq",
                                         description="Reports 5'-footprint properties from 5Pseq reads in a given alignment file")

        # TODO parse arguments for fivepseq count and viz programs separately;
        # TODO implement main accordingly

        subparsers = parser.add_subparsers(help="Use help functions of commands count or plot",
                                           dest="command")

        ##########################
        #       common arguments
        ##########################

        parser.add_argument("-g", "-genome",
                                  help="the full path to the fa/fasta file (may be compressed)",
                                  type=str,
                                  required=True)
        parser.add_argument("-a", "-annotation",
                                  help="the full path to the gtf/gff/gff3 file (may be compressed)",
                                  type=str,
                                  required=True)
        parser.add_argument("--span",
                                  help="the number of bases to span around a genomic position",
                                  type=int,
                                  required=False,
                                  default=100)

        parser.add_argument('--conflicts',
                                  help="The file conflict mode:\n"
                                       "add (default) - only adds missing files to existing directory\n"
                                       "overwrite - overwrites all the files in the existing (in case) output directory\n"
                                       "alt_dir - uses alternative directory by appending '+' suffix to existing (in case) output directory",
                                  type=str,
                                  choices=['add', 'overwrite', 'alt_dir'],
                                  required=False,
                                  default="add")

        parser.add_argument("--log",
                                  help="set logging level",
                                  choices=["INFO", "DEBUG", "info", "debug"],
                                  default="DEBUG",
                                  required=False)

        ##########################
        #       fivepseq count
        ##########################

        count_parser = subparsers.add_parser('count', help="fivepseq count help")

        count_parser.add_argument("-b", "-bam",
                                  help="the full path one or many bam/sam files (many files should be provided with a pattern, within brackets)",
                                  type=str,
                                  required=True)


        count_parser.add_argument("-o", "-outdir",
                                  help="the output directory",
                                  type=str,
                                  required=False,
                                  default="fivepseq_out")


        count_parser.add_argument("-s", "-geneset",
                                  help="the file containing gene names of interest",
                                  type=str,
                                  required=False)

        count_parser.add_argument("--loci-file",
                                  help="file with loci to count mapping positions relative to",
                                  required=False,
                                  type=str)


        count_parser.add_argument("--ignore-cache",
                                  help="read in transcript assembly and rewrite existing pickle paths",
                                  action="store_true",
                                  default=False,
                                  required=False)

        #FIXME not possible to save to pickle path: reason cython reduce not working for pysam Alignment class
        #count_parser.add_argument("--fivepseq-pickle",
        #                          help="specify the pickle path to read in existing FivePSeqCounts object",
        #                          required=False)



        ##########################
        #       fivepseq plot
        ##########################

        plot_parser = subparsers.add_parser('plot', help="fivepseq plot help")

        input_arg_group = plot_parser.add_mutually_exclusive_group(required=True)
        input_arg_group.add_argument("-sd", "-fivepseq_dir",
                                     help="the full path to the fivepseq counts directory",
                                     type=str,
                                     required=False)
        input_arg_group.add_argument("-md", "-multi-fivepseq_dir",
                                     help="the full path to the directory containing fivepseq count directories for multiple sampels",
                                     type=str,
                                     required=False)

        plot_parser.add_argument("-o", "-outdir",
                                 help="the output directory",
                                 type=str,
                                 required=False,
                                 default="fivepseq_plots")

        plot_parser.add_argument("-t", "-title",
                                 help="title of the html file",
                                 type=str,
                                 required=False)

        plot_parser.add_argument("-tf", "-transcript_filter",
                                 help = "Name of filter to apply on transcripts",
                                 type = str,
                                 choices=[VizPipeline.FILTER_TOP_POPULATED,
                                          VizPipeline.FILTER_CANONICAL_TRANSCRIPTS],
                                 required=False)



        ##########################
        #       config setup
        ##########################

        config.args = parser.parse_args()
#        if config.args.command == 'count':
#            config.bam = os.path.abspath(config.args.b)


        #FIXME this imposes necessity to know the span size with which fivepseq was run for further visualization
        config.span_size = config.args.span
        config.genome = os.path.abspath(config.args.g)
        config.annot = os.path.abspath(config.args.a)
        config.out_dir = os.path.abspath(config.args.o)

    def print_args(self):
        """
        Prints the command line arguments in a formatted manner.
        :return:
        """
        # NOTE The files are not checked for existence at this stage.
        # NOTE The absolute_path function simply merges the relative paths with the working directory.
        if config.args.command == 'count':
            print "Call to fivepseq count with arguments:\n"
            print "%s%s" % (pad_spaces("\tAlignment file:"), os.path.abspath(config.args.b))
            print "%s%s" % (pad_spaces("\tGenome file:"), os.path.abspath(config.args.g))
            print "%s%s" % (pad_spaces("\tAnnotation file:"), os.path.abspath(config.args.a))

            print "%s%s" % (pad_spaces("\tSpan size:"), config.span_size)
            if config.args.s is not None:
                print "%s%s" % (pad_spaces("\tGene set file:"), os.path.abspath(config.args.s))
            print "%s%s" % (pad_spaces("\tOutput directory:"), os.path.abspath(config.args.o))
            print "%s%s" % (pad_spaces("\tConflict handling:"), config.args.conflicts)

            print "%s%s" % (pad_spaces("\tLogging level:"), config.args.log.upper())

         #   if config.args.fivepseq_pickle is not None:
         #       print "%s%s" % (pad_spaces("\tFivepseq pickle path specified:"), config.args.fivepseq_pickle)

        elif config.args.command == 'plot':
            print "Call to fivepseq plot with arguments:\n"
            if config.args.sd is not None:
                print "%s%s" % (pad_spaces("\tInput dir:"), os.path.abspath(config.args.sd))
            else:
                if len(glob.glob(config.args.md)) == 0:
                    err_msg = "Provided input %s does not contain proper fivepseq directories" % config.args.md
                    raise Exception(err_msg)
                print "%s" % (pad_spaces("\tInput directories:"))
                #TODO check for proper patterned input
                for f in glob.glob(config.args.md):
                    print "%s" % pad_spaces("\t%s" % f)
            print "%s%s" % (pad_spaces("\tGenome file:"), os.path.abspath(config.args.g))
            print "%s%s" % (pad_spaces("\tAnnotation file:"), os.path.abspath(config.args.a))
            if config.args.o is not None:
                print "%s%s" % (pad_spaces("\tOutput directory:"), os.path.abspath(config.args.o))

            if config.args.t is not None:
                print "%s%s" % (pad_spaces("\tOutput file title:"), config.args.t + ".html")


def setup_output_dir():
    """
    This method attempts to set the output directory for fivepseq count reports.

    If the user-specified output_dir does not exist and the parent directory does, then the output will be stored there.

    If the user-specified output_dir does not exist and the parent directory also, then an IOError is raised.

    If the user-specified output_dir already exists, then the file conflicts are resolved based on the option specified:
        - add (default): only the count files not in the directory are generated and added
        - overwrite:  attempts to remove and replace all the content of the directory. Exception is raised in case of failure.
        - alt_dir: appends "+" signs to the  end of the directory name recursively, until no such directory exists. Creates a new directory and stores the output there.

    :return:
    """

    output_dir = config.out_dir
    if os.path.exists(output_dir):
        if config.args.conflicts == config.ADD_FILES:
            print ("\nWARNING:\tThe output directory %s already exists.\n"
                   "\tOnly missing files will be added." % output_dir)

        if config.args.conflicts == config.OVERWRITE:
            print ("\nWARNING:\tThe output directory %s already exists.\n"
                   "\tOnly missing files will be added." % output_dir)

            #NOTE the output directory is not removed as previously.
            #NOTE Only individual files will be overwritten
            #try:
            #    shutil.rmtree(output_dir)
            #except Exception as e:
            #    error_message = "ERROR:\tCould not remove directory %s. Reason:%s" % (output_dir, e.message)
            #    raise Exception(error_message)
            #make_out_dir(output_dir)

        elif config.args.conflicts == config.ALT_DIR:
            while os.path.exists(output_dir):
                output_dir += "+"
            print "\nWARNING:\tOutput directory %s already exists.\n\tFiles will be stored in %s" % (
                config.out_dir, output_dir)
            config.out_dir = output_dir
            make_out_dir(output_dir)

    else:
        make_out_dir(output_dir)
    # FIXME probably the cache directory should reside somewhere in the fivepseq package folder
    # TODO add checks to make sure the parent directory exists and has write permissions
    # TODO (maybe should not be a problem when it is within the fivepseq package, or not?)
    config.cache_dir = os.path.join(os.path.dirname(config.out_dir), "fivepseq_cache")
    if not os.path.exists(config.cache_dir):
        os.makedirs(config.cache_dir)

def make_out_dir(output_dir):
    try:
        os.makedirs(output_dir)
        print "\n\tSETUP:\tSuccess"
        print "\tSETUP:\t%s%s" % (pad_spaces("Output directory:"), output_dir)
    except Exception as e:
        error_message = "\tSETUP:\tCould not create output directory %s. Reason: %s" % (output_dir, str(e))
        raise Exception(error_message)

def setup_logger():
    """
    Sets up the logger and the handlers for different logging levels.
    Set the logger level according to the argument --log passed to the argparse. Raises a ValueError in case of an invalid argument.
    Raises an exception if the files for handlers cannot be generated.
    :return:
    """
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                        format='%(levelname)s:%(asctime)s\t [%(filename)s:%(lineno)s - %(funcName)s]\t%(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S')

    count_logger = logging.getLogger(config.FIVEPSEQ_COUNT_LOGGER)
    plot_logger = logging.getLogger(config.FIVEPSEQ_PLOT_LOGGER)

    count_log_file = os.path.join(config.out_dir, "fivepseq_count.log")
    plot_log_file = os.path.join(config.out_dir, "fivepseq_plot.log")
    log_level = getattr(logging, config.args.log.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError('Invalid log level: %s' % config.args.log)

    # INFO level file handler
    count_file_handler = logging.FileHandler(count_log_file)
    plot_file_handler = logging.FileHandler(plot_log_file)
    count_logger.addHandler(count_file_handler)
    plot_logger.addHandler(plot_file_handler)
    count_file_handler.setLevel(logging.INFO)
    plot_file_handler.setLevel(logging.INFO)

    if not os.path.exists(count_log_file):
        raise Exception("Could not instantiate the count logger. Exiting.")
    print "\tSETUP:\t%s%s" % (pad_spaces("Log file:"), count_log_file)
    if not os.path.exists(plot_log_file):
        raise Exception("Could not instantiate the plot logger. Exiting.")
    print "\tSETUP:\t%s%s" % (pad_spaces("Log file:"), plot_log_file)

    if log_level == logging.DEBUG:
        count_debug_file = os.path.join(config.out_dir, "fivepseq.count_debug.log")
        plot_debug_file = os.path.join(config.out_dir, "fivepseq.plot_debug.log")
        count_debug_handler = logging.FileHandler(count_debug_file)
        plot_debug_handler = logging.FileHandler(plot_debug_file)
        count_debug_handler.setLevel(logging.DEBUG)
        plot_debug_handler.setLevel(logging.DEBUG)
        count_logger.addHandler(count_debug_handler)
        plot_logger.addHandler(plot_debug_handler)
        if not os.path.exists(count_debug_file):
            raise Exception("Could not instantiate count debug logger. Exiting")
        print "\tSETUP:\t%s%s" % (pad_spaces("Debug file:"), count_debug_file)
        if not os.path.exists(plot_debug_file):
            raise Exception("Could not instantiate plot debug logger. Exiting")
        print "\tSETUP:\t%s%s" % (pad_spaces("Debug file:"), plot_debug_file)


print ""

def load_FivePSeq_from_pickle():
    # FIXME it's not possible to write the FivePSeqCounts object to pickle so the below code is for vein
    pickle_path = config.getFivepseqCountsPicklePath()
    logger = logging.getLogger(config.FIVEPSEQ_COUNT_LOGGER)
    if pickle_path is not None:
        logger.debug("Loading FivePSeqCounts object from existing pickle path %s" % pickle_path)
        try:
            fivepseq_counts = dill.load((open(pickle_path, "rb")))
            logger.debug("Successfully loaded FivePSeqCounts object")
            if fivepseq_counts.span_size != config.span_size:
                logger.warning("The specified span size of %d does not correspond to the size of %d "
                                      "used in the FivePSeq object loaded from existing pickle path. \n"
                                      "The span size of %d will be used."
                                      % (config.span_size, fivepseq_counts.span_size,
                                         fivepseq_counts.span_size))

            return fivepseq_counts
        except Exception as e:
            warning_message = "Problem loading FivePSeqCounts object from pickle path %s. Reason: %s\n" \
                              "Fivepseq will generate a new FivePSeqCounts object." % (
                                  pickle_path, str(e))
            logger.warning(warning_message)


def save_fivepseq_counts_to_pickle(fivepseq_counts):
    # TODO save fivepseq_counts in pickle_path
    pickle_path = config.generateFivepseqPicklePath()
    logger = logging.getLogger(config.FIVEPSEQ_COUNT_LOGGER)
    if os.path.exists(pickle_path):
        try:
            os.remove(pickle_path)
        except Exception as e:
            logger.error("Could not remove previous fivepseq object from pickle path: %s"
                                % pickle_path)
    # FIXME cannot write dill object because of error: no default __reduce__ due to non-trivial __cinit__

    with open(pickle_path, "wb") as dill_file:
        dill.dump(fivepseq_counts, dill_file)
    logger.debug("Dumped FivePSeqCounts object to file %s" % pickle_path)

def generate_and_store_fivepseq_counts():
    logger = logging.getLogger(config.FIVEPSEQ_COUNT_LOGGER)
    logger.info("Fivepseq count started")

    #fivepseq_counts = load_FivePSeq_from_pickle()
    fivepseq_counts = None

    if fivepseq_counts is None:
        # read files
        annotation_reader = AnnotationReader(config.annot)  # set the break for human
        fasta_reader = FastaReader(config.genome)

        if config.args.loci_file is not None:
            fivepseq_counts.loci_file = config.args.loci_file

        print "%s" % (pad_spaces("\tInput bam files:"))
        bam_files = []
        for bam in glob.glob(config.args.b):
            if bam.endswith(".bam"):
                bam_files.append(bam)
                print "%s" % pad_spaces("\t%s" % bam)

        success_values = {}
        for bam in bam_files:
            bam_reader = BamReader(bam)
            # combine objects into FivePSeqCounts object
            fivepseq_counts = FivePSeqCounts(bam_reader.alignment, annotation_reader.annotation, fasta_reader.genome,
                                             config.span_size)

            bam_name = os.path.basename(bam)
            if bam_name.endswith(".bam"):
                bam_name = bam_name[0:len(bam_name)-4]
            bam_out_dir = os.path.join(config.out_dir, bam_name)
            if not os.path.exists(bam_out_dir):
                os.mkdir(bam_out_dir)

            fivepseq_out = FivePSeqOut(bam_out_dir, config.args.conflicts)
            fivepseq_pipeline = CountPipeline(fivepseq_counts, fivepseq_out)
            fivepseq_pipeline.run()
            success = fivepseq_out.sanity_check_for_counts()
            if success:
                success_values.update({bam_name: "SUCCESS"})
            else:
                success_values.update({bam_name: "FAILURE"})

        # check if all the files in all directories are in place and store a summary of all runs
        fivepseq_out = FivePSeqOut(config.out_dir, config.OVERWRITE) # overwrite is for always removing existing summary file
        fivepseq_out.write_dict(success_values, FivePSeqOut.BAM_SUCCESS_SUMMARY)


    return fivepseq_counts


def generate_plots():
    logger = logging.getLogger(config.FIVEPSEQ_PLOT_LOGGER)
    logger.info("Fivepseq plot started")

    viz_pipeline = VizPipeline(config.args)
    viz_pipeline.run()

    if config.args.sd is not None:
        print "Single sample %s provided" % config.args.sd
    else:
        print "Multiple samples in %s provided" % config.args.md


    # scatterplots.plot_frames_term(fivepseq_counts, FivePSeqCounts.TERM,
    # os.path.join(config.out_dir, "meta_count_frames.pdf"))
    # scatterplots.plot_frames_term(fivepseq_counts, FivePSeqCounts.START,
    # os.path.join(config.out_dir, "meta_count_frames_start.pdf"))

    pass


def main():
    # argument handling
    fivepseq_arguments = FivepseqArguments()
    fivepseq_arguments.print_args()

    # startup
    setup_output_dir()
    setup_logger()

    start_time = time.clock()

    # body
    if config.args.command == 'count':
        count_logger = logging.getLogger(config.FIVEPSEQ_COUNT_LOGGER)
        count_logger.info("Fivepseq count started")
        generate_and_store_fivepseq_counts()
        elapsed_time = time.clock() - start_time
        count_logger.info("SUCCESS! Fivepseq count finished in\t%s\tseconds. The report files maybe accessed at:\t\t%s "
                       % (elapsed_time, config.out_dir))

    elif config.args.command == 'plot':
        plot_logger = logging.getLogger(config.FIVEPSEQ_PLOT_LOGGER)
        plot_logger.info("Fivepseq plot started")
        generate_plots()
        elapsed_time = time.clock() - start_time
        if config.args.t is not None:
            title = config.args.t
        else:
            if config.args.sd is not None:
                title = os.path.basename(config.args.sd)
            else:
                title = os.path.basename(os.path.dirname(config.args.md)) + "_" + os.path.basename(config.args.md)

        plot_logger.info("SUCCESS! Fivepseq plot finished in\t%s\tseconds. "
                         "The report files maybe accessed at:\t\t%s/%s "
                       % (elapsed_time, config.out_dir, title))


    # TODO handle KeyboardInterrupt's (try, wait, except, pass?)


if __name__ == '__main__':
    main()
